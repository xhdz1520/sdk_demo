"""Original FR8000 ota.c commands over USB CDC."""
import struct
import time
from pathlib import Path
FLASH_SIZE = 1024 * 1024 * 8 #512 * 1024
SECTOR = 4096
CHUNK = 256

def sdk_crc(data):
    """Exact SDK Crc32CalByByte; this is NOT zlib.crc32."""
    crc = 0
    for byte in data:
        signed = crc if crc < 0x80000000 else crc - 0x100000000
        high = signed // 256 if signed >= 0 else -((-signed) // 256)
        v = (high ^ byte) & 255
        for _ in range(8):
            v = (v >> 1) ^ (0xEDB88320 if v & 1 else 0)
        crc = ((crc << 8) ^ v) & 0xFFFFFFFF
    return crc


def load_firmware(path):
    data = Path(path).read_bytes()
    if len(data) <= 0x2000:
        raise ValueError("固件过短，应选择包含 jump table 的完整 SDK .bin")
    size, image_type = struct.unpack_from('<II', data, 4)
    if image_type != 0x33333333:
        raise ValueError("不是 SDK APP 镜像（image_type 错误）")
    if size % SECTOR or size < len(data) or size > FLASH_SIZE // 2:
        raise ValueError("镜像头分区大小无效或小于文件，请检查 .image_size")
    if data[0x60:0x64] != bytes.fromhex('51 52 52 51'):
        raise ValueError("固件 0x60 处缺少文档规定的有效标志 51 52 52 51")
    return data


class ProtocolError(RuntimeError):
    pass


ERRORS = {
    1: '命令长度或参数错误', 2: 'USB 半包接收超时',
    3: 'OTA 会话空闲超时', 4: 'USB 应答发送超时',
    5: 'os_malloc 内存分配失败', 6: 'USB 接收缓冲区溢出',
    7: '原 OTA 地址连续性检查失败或擦除地址低于 B 区',
    8: '原 OTA CRC32 校验失败', 9: '命令处理超时',
}


class OtaClient:
    def __init__(self, port, log=None):
        self.port = port
        self.log = log or (lambda message: None)

    def exact(self, size, deadline):
        data = bytearray()
        while len(data) < size:
            if time.monotonic() >= deadline:
                raise ProtocolError("等待设备应答超时；关闭并重新打开串口后重试")
            part = self.port.read(size - len(data))
            if part:
                data.extend(part)
        return bytes(data)

    def command(self, opcode, payload=b'', timeout=10):
        context = '命令 0x%02X' % opcode
        if opcode in (3, 5, 6) and len(payload) >= 4:
            context += '，地址 0x%08X' % struct.unpack_from('<I', payload)[0]
        if opcode in (5, 6) and len(payload) >= 6:
            context += '，长度 %d' % struct.unpack_from('<H', payload, 4)[0]
        ota_packet = struct.pack('<BH', opcode, len(payload)) + payload
        packet = struct.pack('<H', len(ota_packet)) + ota_packet
        deadline = time.monotonic() + timeout
        self.log('发送 ' + context)
        try:
            sent = 0
            while sent < len(packet):
                if time.monotonic() >= deadline:
                    raise ProtocolError('串口发送总超时')
                n = self.port.write(packet[sent:])
                if not n:
                    raise ProtocolError('串口发送失败')
                sent += n
            envelope_size, = struct.unpack('<H', self.exact(2, deadline))
            if not 4 <= envelope_size <= 512:
                raise ProtocolError('USB 应答包长度错误：%d' % envelope_size)
            response = self.exact(envelope_size, deadline)
            result, original, size = struct.unpack_from('<BBH', response)
            if size != envelope_size-4:
                raise ProtocolError('OTA 应答长度和 USB 包长度不一致')
            data = response[4:]
            if result:
                detail = ERRORS.get(data[0], '未知设备错误') if data else '旧版本通用错误，设备未提供原因'
                raise ProtocolError('设备错误 %d，应答命令 0x%02X：%s；原始应答 %s' %
                                    (result, original, detail, data.hex()))
            if original != opcode:
                raise ProtocolError('应答命令不匹配：0x%02X' % original)
            return data
        except Exception as exc:
            raise ProtocolError(context + '：' + str(exc)) from exc

    def upgrade(self, image, progress):
        declared, = struct.unpack_from('<I', image, 4)
        checksum = sdk_crc(image[256:])
        self.log('文件 %d 字节，声明镜像区 %d 字节，SDK CRC32=0x%08X' %
                 (len(image), declared, checksum))
        self.port.reset_input_buffer()
        version_data = self.command(2, bytes(4))
        if len(version_data) != 4:
            raise ProtocolError('版本号应答长度错误')
        self.log('当前固件版本 0x%08X' % struct.unpack('<I', version_data)[0])
        response = self.command(1, bytes(4))
        if len(response) != 4:
            raise ProtocolError('B 区地址应答长度错误')
        base, = struct.unpack('<I', response)
        erase_length = (len(image) + SECTOR-1) // SECTOR * SECTOR
        if base < 0x2000 or base % SECTOR or base + erase_length > FLASH_SIZE:
            raise ProtocolError('设备返回的 A/B 地址越界：0x%08X' % base)
        if declared > base or len(image) > base:
            raise ProtocolError('新镜像大于当前 A 区，需先通过下载器调整分区')
        self.log('B 区 0x%08X，擦除 %d 字节，按文件实际长度写入' % (base, erase_length))
        for offset in range(0, erase_length, SECTOR):
            address = struct.pack('<I', base + offset)
            if self.command(3, address) != address:
                raise ProtocolError('擦除地址应答不一致：0x%08X' % (base+offset))
            progress('erase', offset+SECTOR, erase_length)
        for offset in range(0, len(image), CHUNK):
            chunk = image[offset:offset+CHUNK]
            header = struct.pack('<IH', base+offset, len(chunk))
            if self.command(5, header+chunk) != header:
                raise ProtocolError('写入地址或长度应答不一致：0x%08X' % (base+offset))
            progress('write', offset+len(chunk), len(image))
        progress('crc', 0, 1)
        self.command(9, struct.pack('<II', len(image), checksum), timeout=35)
        progress('done', 1, 1)
