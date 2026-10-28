/* CDC envelope: [OTA packet size:u16 LE][unaltered ota.c packet].
 * ISR assembles one packet; the main loop calls app_otas_recv_data once.
 * Two heap buffers separate the ISR receiver from the current command.
 */
#include <string.h>
#include "usb_ota.h"
#include "ota.h"
#include "ota_service.h"
#include "os_mem.h"
#include "driver_timer.h"
#include "driver_system.h"
#include "usb_cdc.h"

extern volatile bool COM_Activate;
extern void ota_timer_timeout(void);
static uint8_t *rx_packet, *work_packet;
static volatile uint16_t expected, received;
static volatile uint8_t length_bytes;
static volatile bool packet_ready, rx_activity, reset_pending, receive_error;
static volatile bool timer_expired;
static uint8_t last_opcode=0xff, last_error;

void usb_ota_timer_stop(void)
{
    GLOBAL_INT_DISABLE();
    timer_stop(Timer1); timer_int_clear(Timer1);
    NVIC_ClearPendingIRQ(TIMER1_IRQn);
    timer_expired=false;
    GLOBAL_INT_RESTORE();
}
void usb_ota_timer_start(uint32_t milliseconds)
{
    GLOBAL_INT_DISABLE();
    timer_stop(Timer1); timer_int_clear(Timer1);
    NVIC_ClearPendingIRQ(TIMER1_IRQn);
    timer_expired=false;
    timer_init(Timer1,(system_get_clock()/1000u)*milliseconds,TIMER_DIV_NONE);
    timer_start(Timer1);
    GLOBAL_INT_RESTORE();
}
void timer1_isr(void)
{
    timer_int_clear(Timer1); timer_stop(Timer1);
    timer_expired=true; /* ota_stop and os_free run in the main loop. */
}
void usb_ota_reset_isr(void)
{
    expected=received=0; length_bytes=0; packet_ready=false;
    receive_error=false; rx_activity=false; reset_pending=true;
}
void usb_ota_link_state_isr(bool active)
{
    (void)active;
    usb_ota_reset_isr();
}
bool usb_ota_init(void)
{
    rx_packet=os_malloc(USB_OTA_MAX_PACKET);
    work_packet=os_malloc(USB_OTA_MAX_PACKET);
    if(!rx_packet || !work_packet || !usb_cdc_ota_memory_init()) {
        usb_ota_shutdown(); return false;
    }
    __SYSTEM_TIMER_CLK_ENABLE();
    usb_ota_timer_stop();
    NVIC_SetPriority(TIMER1_IRQn,1); NVIC_EnableIRQ(TIMER1_IRQn);
    ota_init(0);
    return true;
}
void usb_ota_shutdown(void)
{
    uint8_t *rx, *work;
    GLOBAL_INT_DISABLE();
    rx=rx_packet; work=work_packet;
    rx_packet=work_packet=NULL;
    GLOBAL_INT_RESTORE();
    NVIC_DisableIRQ(TIMER1_IRQn);
    ota_deinit(0);
    if(rx) os_free(rx);
    if(work) os_free(work);
    usb_cdc_ota_memory_deinit();
}
void usb_ota_rx_isr(const uint8_t *data, uint16_t len)
{
    if(!rx_packet || !COM_Activate || receive_error) return;
    rx_activity=true;
    while(len--) {
        if(packet_ready) { receive_error=true; return; }
        if(length_bytes<2) {
            if(length_bytes==0) expected=*data++;
            else expected|=(uint16_t)*data++ << 8;
            length_bytes++;
            if(length_bytes==2 && (!expected || expected>USB_OTA_MAX_PACKET)) {
                receive_error=true; return;
            }
        } else {
            rx_packet[received++]=*data++;
            if(received==expected) packet_ready=true;
        }
    }
}
/* Raw CDC sender. Bounded by the same TIMER1 timeout used by the OTA session. */
bool usb_cdc_send_data(const uint8_t *data, uint16_t len)
{
    uint16_t offset=0, n;
    bool done=false, zlp=(len%64)!=0;
    usb_ota_timer_start(OTA_TIMEOUT);
    while(!done && COM_Activate && !timer_expired) {
        GLOBAL_INT_DISABLE();
        usb_selecet_endpoint(ENDPOINT_1);
        if(!usb_Endpoints_GET_TxPkrRdy()) {
            if(offset<len) {
                n=len-offset; if(n>64) n=64;
                usb_write_fifo(ENDPOINT_1,(uint8_t *)data+offset,n);
                offset+=n; usb_Endpoints_SET_TxPktRdy();
            } else if(!zlp) {
                usb_write_fifo(ENDPOINT_1,(uint8_t *)data,0);
                usb_Endpoints_SET_TxPktRdy(); zlp=true;
            } else done=true;
        }
        GLOBAL_INT_RESTORE();
    }
    return done;
}
static bool send_packet(const uint8_t *data, uint16_t len)
{
    bool sent;
    uint8_t *packet=os_malloc(len+2u);
    if(!packet) return false;
    packet[0]=len; packet[1]=len>>8;
    memcpy(packet+2,data,len);
    sent=usb_cdc_send_data(packet,len+2u);
    os_free(packet);
    return sent;
}
void ota_gatt_report_notify(uint8_t conidx, uint8_t *data, uint16_t len)
{
    (void)conidx;
    if(!last_error) send_packet(data,len);
}
static void send_error(uint8_t reason)
{
    uint8_t response[5]={OTA_RSP_ERROR,0,1,0,0};
    response[1]=last_opcode; response[4]=reason;
    send_packet(response,sizeof(response));
}
void usb_ota_warning(uint8_t warning)
{
    last_error=warning==OTA_CHECK_FAIL ? 8 : warning==OTA_ADDR_ERROR ? 7 : 3;
    /* CRC failure calls usb_ota_reboot immediately in the original ota.c. */
    if(warning!=OTA_CHECK_FAIL) { send_error(last_error); usb_ota_timer_stop(); }
}
void usb_ota_reboot(uint32_t error)
{
    /* Original ota.c owns CRC and A/B metadata. Only report its result first. */
    uint8_t response[4]={OTA_RSP_SUCCESS,OTA_CMD_REBOOT,0,0};
    if(last_error) send_error(last_error);
    else send_packet(response,sizeof(response));
    platform_reset(error);
    while(1); /* Same non-returning contract as platform_reset in ota.c. */
}
void usb_ota_poll(void)
{
    uint8_t *packet;
    uint16_t len;
    bool reset;
    {
    GLOBAL_INT_DISABLE();
    reset=reset_pending; reset_pending=false;
    GLOBAL_INT_RESTORE();
    }
    if(reset) { usb_ota_timer_stop(); ota_deinit(0); ota_init(0); last_error=0; last_opcode=0xff; }
    if(timer_expired) {
        GLOBAL_INT_DISABLE();
        expected=received=0; length_bytes=0; packet_ready=false;
        GLOBAL_INT_RESTORE();
        ota_timer_timeout();
        usb_ota_timer_stop();
    }
    if(rx_activity) { rx_activity=false; usb_ota_timer_start(OTA_TIMEOUT); }
    if(receive_error) {
        usb_ota_reset_isr(); send_error(1); return;
    }
    if(!packet_ready) return;
    GLOBAL_INT_DISABLE();
    packet=rx_packet; rx_packet=work_packet; work_packet=packet;
    len=received;
    expected=received=0; length_bytes=0; packet_ready=false;
    GLOBAL_INT_RESTORE();
    /* The CDC envelope must contain one complete, ordinary OTA command. */
    last_opcode=packet[0]; last_error=0;
    if(len<3 || len!=(uint16_t)(3u+packet[1]+((uint16_t)packet[2]<<8))) {
        send_error(1); return;
    }
    /* Check only buffer lengths before passing a packet to the original parser. */
    if((last_opcode==OTA_CMD_PAGE_ERASE && len!=7) ||
       (last_opcode==OTA_CMD_REBOOT && len!=11) ||
       (last_opcode==OTA_CMD_WRITE_DATA &&
        (len<9 || (uint16_t)(packet[7]+((uint16_t)packet[8]<<8))!=len-9))) {
        send_error(1); return;
    }
    app_otas_recv_data(0,packet,len);
}
