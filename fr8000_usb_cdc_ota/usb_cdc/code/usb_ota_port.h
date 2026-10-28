#ifndef USB_OTA_PORT_H
#define USB_OTA_PORT_H
#include "usb_ota.h"
#include "ota.h"
/* Only the BLE transport calls are replaced. ota.c's dispatcher is unchanged. */
#define gap_conn_param_update(...) ((void)0)
#define gatt_mtu_exchange_req(...) ((void)0)
#define gatt_get_mtu(...) USB_OTA_MAX_PACKET
#define gap_disconnect_req(...) usb_ota_warning(OTA_ADDR_ERROR)
#endif
