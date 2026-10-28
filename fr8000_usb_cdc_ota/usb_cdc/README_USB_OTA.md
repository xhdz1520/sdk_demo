# USB CDC OTA（原 ota.c 接口移植版）

工程已安装到 `D:\WorkFiles\FR800U\fr8000_sdk_V2.1\examples\none_evm\peripheral_demo\usb_cdc`。

## 代码结构

- `code/ota.c`、`ota.h`、`ota_service.h`、`crc32.h`：从 SDK `components/ble/profiles/ble_ota` 复制。Flash 擦写、写保护、地址检查、CRC 算法及 A/B 镜像提交均保留原实现。
- `code/usb_ota.c`：USB 包收发封装、完整包调用 `app_otas_recv_data(0, packet, len)`、TIMER1 超时处理。
- `code/usb_ota_port.h`：屏蔽 BLE 连接参数/MTU 操作，将断开通知转为 USB 错误提示。
- `code/usb_cdc_ota_transport.c`：USB OUT 数据交给组包接口；原 UART 透传取消。SDK 公共 `components/driver/usb_cdc.c` 未改。
- `host/ota_gui.py`、`ota_protocol.py`：按 PDF 的顺序完成版本查询、获取 B 区地址、擦除、写入、CRC 校验和重启。

原 `ota.c` 的全部差异见 `ota_port.diff`：替换 BLE 头文件、把 `os_timer` 换成 TIMER1、增加错误上报钩子，以及把重启接口包装为“先回传原 OTA 的结果，再重启”。未重写命令处理。`ota.h` 开启原有 `OTA_CRC_CHECK` 分支。

直接调用工程自带的 `os_malloc/os_free`；没有自建堆、没有调用 `ke_mem_init`、没有修改 SDK 链接脚本。启动时按 SDK 示例调用 `ble_stack_configure/ble_stack_init`，保证工程自带动态内存可用。收发缓冲使用动态内存，原始只读 USB 描述符、CRC 表及工程系统栈保留。

## USB 外层组包

USB CDC 是字节流，用一个简单外层区分完整 OTA 包：

```text
[OTA 包总长度：2 字节小端] [原始 OTA 包]
```

双向均采用此格式。单个原始 OTA 包不超过 512 字节，主机每发一包必须等待一包响应。OUT 中断只组包；主循环取完整包，直接调用原 OTA 命令处理函数。内层格式和 PDF 相同：

```text
请求：[opcode:u8][payload_length:u16 LE][payload]
响应：[result:u8][original_opcode:u8][payload_length:u16 LE][payload]
```

例如文档的获取 B 区地址命令：内层 `01 04 00 00 00 00 00`，USB 实际发送 `07 00 01 04 00 00 00 00 00`。

`ota_gatt_report_notify()` 的实现改为经 CDC 回包，原函数调用位置不变。上位机按文档发送 `0x02/0x01` 的四字节占位参数，逐 4 KB 擦除 bin 实际占用的空间，再按 256 字节分包发送 `0x05`；最后的 `0x09` 发送 **bin 实际长度**及去掉前 256 字节后的原 SDK CRC。不会补齐 bin 后再发送，也不额外添加写入读回流程。文件选择时检查文档规定的 `0x60` 位置有效标志 `51 52 52 51`。

## TIMER1

保留原 `OTA_TIMEOUT=5000 ms`：收到数据和原 OTA 接收函数会重启 TIMER1；发送应答也使用同一超时限制。TIMER1 中断只置超时标志，主循环调用原超时回调及 `ota_stop(OTA_TIMOUT)`。串口关闭/USB 复位时调用原 `ota_deinit/ota_init`。

原 `ota.c` 在 CRC 失败时也会重启，这一行为保留；上位机会先收到失败响应并显示失败。只有原 OTA 校验、B 区元数据提交完成后的成功响应，才显示绿色成功。成功响应表示已校验并提交，不代表已经检查新程序重启后的运行状态。

## 使用

1. Keil 打开 `proj/peripheral_demo.uvproj` 编译。生成 `proj/peripheral_demo.bin`。
2. **用下载器烧录本次新固件**，旧版应用和本次 Python 上位机的 USB 外层协议不兼容。
3. 安装依赖：`python -m pip install -r host/requirements.txt`。
4. 双击 `host/start_ota.bat`，扫描并打开目标 USB CDC COM 口，选择完整 SDK APP bin，开始升级。
5. 界面显示擦除、写入进度、CRC 状态、成功标签及异常。日志包含命令号、Flash 地址和长度。报错后关闭并重新打开串口重试。

当前沿用此前工程的 `.image_size=0x30000`（192 KB），本次未再次改变分区。新固件也需要包含此 USB OTA 接口，才能继续通过 USB 升级。

## 验证

Keil 结果见 `keil_build.log`。`python -m unittest discover -s tests -v` 检查真实 `ota.c` 与适配层在 Flash/USB/TIMER1 测试桩下的升级、分包、CRC、超时及协议行为；测试桩中的数组不属于固件。

未对实际设备执行烧录、擦写或重启测试。

## 看门狗复位

`usb_ota_reboot()` 发送升级结果后停止 TIMER1、屏蔽中断，使用 SDK `wdt_init()` 启动 PMU 看门狗：`WdtCount=3200`、`Timeout=0xFF`、`IRQ_Enable=WDT_IRQ_DISABLE`，随后等待硬件复位且不喂狗。计数阶段约 100 ms，另加硬件超时尾段。OTA Flash、CRC 和 A/B 提交代码未改。

若当前运行的是之前不会自动重启的版本，通过旧版 OTA 刷入本版后仍需手动复位一次；新版本启动后，后续升级才会调用新的看门狗复位接口。也可以通过下载器直接烧录并复位。
