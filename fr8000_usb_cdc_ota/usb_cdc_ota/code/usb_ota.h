#ifndef USB_OTA_H
#define USB_OTA_H
#include <stdint.h>
#include <stdbool.h>
#define USB_OTA_MAX_PACKET 512u
bool usb_ota_init(void);
void usb_ota_shutdown(void);
void usb_ota_poll(void);
void usb_ota_rx_isr(const uint8_t *data, uint16_t len);
void usb_ota_reset_isr(void);
void usb_ota_link_state_isr(bool active);
bool usb_cdc_send_data(const uint8_t *data, uint16_t len);
void usb_ota_timer_start(uint32_t milliseconds);
void usb_ota_timer_stop(void);
void usb_ota_warning(uint8_t warning);
void usb_ota_reboot(uint32_t error);
bool usb_cdc_ota_memory_init(void);
void usb_cdc_ota_memory_deinit(void);
#endif
