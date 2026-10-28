# ---------------------------------- #
#    GCC Bulid command log config    #
# ---------------------------------- #
#CMD_LOG = 1

# echo suspend
ifdef CMD_LOG
  NO_ECHO = 
else
  NO_ECHO = @
endif

SYSTEM := $(filter Windows_NT, $(OS))

# ---------------------------------- #
# Project name                       #
# ---------------------------------- #
PROJECT_NAME := fr8000_project

# ---------------------------------- #
# Path config                        #
# ---------------------------------- #
TOP_DIR     := ../../../../..
PROJECT_DIR := ../code
OBJECT_DIR  := Objects

# ---------------------------------- #
# Toolchain config                   #
# ---------------------------------- #
TOOLCHAIN := arm-none-eabi

CC      := $(TOOLCHAIN)-gcc
AS      := $(TOOLCHAIN)-as
LD      := $(TOOLCHAIN)-ld
OBJDUMP := $(TOOLCHAIN)-objdump
OBJCOPY := $(TOOLCHAIN)-objcopy
SIZE    := $(TOOLCHAIN)-size

# ---------------------------------- #
# ld/lib config                      #
# ---------------------------------- #
LD   := $(TOP_DIR)/components/toolchain/gcc/ldscript.ld
LD_C := $(TOP_DIR)/components/ble/library/syscall_gcc.txt
LIB  := $(TOP_DIR)/components/ble/library/libfr800x_stack.a

# ---------------------------------- #
# Source files config                #
# ---------------------------------- #
SRC_FILES += $(TOP_DIR)/examples/none_evm/peripheral_demo/usb_cdc/code/proj_main.c
SRC_FILES += $(TOP_DIR)/examples/none_evm/peripheral_demo/usb_cdc/code/usb_demo.c

SRC_FILES += $(TOP_DIR)/components/driver/driver_pmu.c
SRC_FILES += $(TOP_DIR)/components/driver/driver_gpio.c
SRC_FILES += ../code/usb_cdc_ota_transport.c
SRC_FILES += ../code/usb_ota.c
SRC_FILES += ../code/ota.c
SRC_FILES += $(TOP_DIR)/components/driver/driver_timer.c
SRC_FILES += $(TOP_DIR)/components/driver/driver_wdt.c
SRC_FILES += $(TOP_DIR)/components/driver/usb_core.c
SRC_FILES += $(TOP_DIR)/components/driver/usb_dev.c

SRC_FILES += $(TOP_DIR)/components/toolchain/gcc/boot_vectors.c
SRC_FILES += $(TOP_DIR)/components/modules/common/src/co_log.c


# ---------------------------------- #
# Include path config                #
# ---------------------------------- #
INC_PATH += -I"$(TOP_DIR)/components/driver/include"
INC_PATH += -I"$(TOP_DIR)/components/driver/drv_common"
INC_PATH += -I"$(TOP_DIR)/components/driver/components/display"
INC_PATH += -I"$(TOP_DIR)/components/driver/components/spi_flash"
INC_PATH += -I"$(TOP_DIR)/components/driver/components/touchpad"
INC_PATH += -I"$(TOP_DIR)/components/modules/platform/include"
INC_PATH += -I"$(TOP_DIR)/components/modules/platform/include/cmsis"
INC_PATH += -I"$(TOP_DIR)/components/modules/common/include"
INC_PATH += -I"$(TOP_DIR)/components/modules/sys/include"
INC_PATH += -I"$(TOP_DIR)/components/modules/os/include"
INC_PATH += -I"$(TOP_DIR)/components/ble/include"
INC_PATH += -I"$(TOP_DIR)/components/ble/include/gap"
INC_PATH += -I"$(TOP_DIR)/components/ble/include/gatt"
INC_PATH += -I"$(TOP_DIR)/components/ble/include/mesh"

INC_PATH += -I"$(PROJECT_DIR)"

# ----------------------------------- #
# Objects files common to all targets #
# ----------------------------------- #
BASE_SRC  = $(notdir $(SRC_FILES)) 
BASE_OBJS = $(BASE_SRC:%.c=%.o)
OBJS      = $(BASE_OBJS:%.o=$(OBJECT_DIR)/%.o)

BASE_ElF  = $(OBJECT_DIR)/$(PROJECT_NAME).elf

# ---------------------------------- #
# Source files path                  #
# ---------------------------------- #
VPATH = $(dir $(SRC_FILES)) 

# ---------------------------------- #
# C flags common to all targets      #
# ---------------------------------- #
CFLAGS += -mcpu=cortex-m3
CFLAGS += -mthumb
CFLAGS += -O3
CFLAGS += -fmessage-length=0 -fsigned-char
CFLAGS += -ffunction-sections -fdata-sections
CFLAGS += -g3
CFLAGS += -std=gnu11

# ---------------------------------- #
# LD flags common to all targets     #
# ---------------------------------- #
LDFLAGS += -mcpu=cortex-m3
LDFLAGS += -mthumb
LDFLAGS += -O3
LDFLAGS += -fmessage-length=0 -fsigned-char
LDFLAGS += -ffunction-sections -fdata-sections
LDFLAGS += -g3
LDFLAGS += -Xlinker --gc-sections
LDFLAGS += --specs=nosys.specs -u _printf_float


# ---------------------------------- #
# all target list                    #
# ---------------------------------- #
all: Target_Path Target_OBJS Target_ELF Target_DONE

# ---------------------------------- #
# Create Path                        #
# ---------------------------------- #
Target_Path :
	$(shell if [ ! -d $(OBJECT_DIR) ];then mkdir $(OBJECT_DIR); fi)

# ---------------------------------- #
# compile .c .s                      #
# ---------------------------------- #
Target_OBJS : $(OBJS)

$(OBJECT_DIR)/%.o : %.c
	$(info Bulid: compiling $^)
	$(NO_ECHO)$(CC) $(CFLAGS) $(INC_PATH) -c -o  $@ $<

$(OBJECT_DIR)/%.o : %.s
	$(info Bulid: compiling $^)
	$(NO_ECHO)$(CC) $(CFLAGS) $(INC_PATH) -c -o  $@ $<

# ---------------------------------- #
# Create Image File                  #
# ---------------------------------- #
Target_ELF : $(BASE_ElF)

$(BASE_ElF) : $(OBJS)
	$(NO_ECHO)$(CC) $(LDFLAGS) -T $(LD) -T $(LD_C) -Wl,-Map,"$(PROJECT_NAME).map" -o $(OBJECT_DIR)/$(PROJECT_NAME).elf $^ $(LIB)
	$(NO_ECHO)$(OBJCOPY) -O binary -S $(OBJECT_DIR)/$(PROJECT_NAME).elf $(PROJECT_NAME).bin
	$(NO_ECHO)$(OBJCOPY) -O ihex   -S $(OBJECT_DIR)/$(PROJECT_NAME).elf $(PROJECT_NAME).hex
	$(NO_ECHO)$(OBJDUMP) -D $(OBJECT_DIR)/$(PROJECT_NAME).elf > $(PROJECT_NAME).dis
	$(info Bulid: creating $(OBJECT_DIR)/$(PROJECT_NAME).elf)
	$(info Bulid: creating $(PROJECT_NAME).map)
	$(info Bulid: creating $(PROJECT_NAME).bin)
	$(info Bulid: creating $(PROJECT_NAME).hex)
	$(info Bulid: creating $(PROJECT_NAME).dis)

# ---------------------------------- #
# Output image file size             #
# ---------------------------------- #
.PHONY : Target_DONE
Target_DONE:
	@echo Bulid: Output image file info:
	$(NO_ECHO)$(SIZE) $(OBJECT_DIR)/$(PROJECT_NAME).elf
	@echo Bulid: $(PROJECT_NAME) make done.

# ---------------------------------------- #
# delete file(.o .elf .bin .dis .hex .map) #
# ---------------------------------------- #
.PHONY : clean

clean :
	$(NO_ECHO)rm -rf $(OBJECT_DIR) *.elf *.bin *.dis *.hex *.map
	@echo delete *.o *.elf *.bin *.dis *.hex *.map
