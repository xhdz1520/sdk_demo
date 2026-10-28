/*
  ******************************************************************************
  * @file    usb_demo.c
  * @author  FreqChip Firmware Team
  * @version V1.0.0
  * @date    2021
  * @brief   USB module Demo.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2021 FreqChip.
  * All rights reserved.
  ******************************************************************************
*/
#include "usb_demo.h"

#include "driver_gpio.h"
#include "driver_spi.h"
#include "driver_system.h"
#include "driver_pmu.h"

#include "co_printf.h"
#include "co_log.h"
#include "sys_utils.h"
#include "ble_stack.h"

#include "usb_cdc.h"
#include "usb_ota.h"

/************************************************************************************
 * @fn      usb_demo
 *
 * @brief   usb demo
 */
void usb_demo(void)
{
    co_printf("USB OTA buffer init begin\r\n");
    if(!usb_ota_init()) {
        co_printf("USB OTA heap allocation failed\r\n");
        return;
    }
    co_printf("USB OTA buffer init done\r\n");
    pmu_usb_pad_ctrl(true);
    
	NVIC_ClearPendingIRQ(USBMCU_IRQn);
	/* SDK GLOBAL_INT_DISABLE uses BASEPRI=0x20; priority 0 bypasses it. */
	NVIC_SetPriority(USBMCU_IRQn, 2);
	NVIC_EnableIRQ(USBMCU_IRQn);

	usb_device_init();
	usb_cdc_init();

	usb_DP_Pullup_Enable();
	co_printf("USB CDC pullup enabled\r\n");

	while(1)
	{
		usb_cdc_serialReceive();
	}
}

