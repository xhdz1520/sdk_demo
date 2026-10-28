import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("缺少依赖", "请执行：python -m pip install -r requirements.txt")
    raise SystemExit(1)

from ota_protocol import OtaClient, load_firmware


class App:
    def __init__(self, root):
        self.root = root
        root.title("FR8000 USB CDC OTA")
        root.geometry("800x540")
        self.port = None
        self.busy = False
        self.events = queue.Queue()
        self.firmware = tk.StringVar()
        self.status = tk.StringVar(value="请选择串口并打开")
        self.stage = tk.StringVar(value="待升级")
        main = ttk.Frame(root, padding=18)
        main.pack(fill='both', expand=True)
        row = ttk.Frame(main)
        row.pack(fill='x', pady=6)
        ttk.Label(row, text="串口").pack(side='left')
        self.ports = ttk.Combobox(row, width=18, state='readonly')
        self.ports.pack(side='left', padx=6)
        self.scan_button = ttk.Button(row, text="扫描串口", command=self.scan)
        self.scan_button.pack(side='left')
        ttk.Label(row, text="波特率").pack(side='left', padx=(15, 4))
        self.baud = ttk.Combobox(row, values=['9600', '57600', '115200', '230400', '460800', '921600'], width=10)
        self.baud.set('115200')
        self.baud.pack(side='left')
        self.open_button = ttk.Button(row, text="打开串口", command=self.toggle)
        self.open_button.pack(side='left', padx=6)
        ttk.Label(main, textvariable=self.status).pack(anchor='w', pady=8)
        row = ttk.Frame(main)
        row.pack(fill='x', pady=8)
        ttk.Entry(row, textvariable=self.firmware, state='readonly').pack(side='left', fill='x', expand=True)
        self.choose_button = ttk.Button(row, text="选择固件 .bin", command=self.choose)
        self.choose_button.pack(side='left', padx=6)
        self.start_button = ttk.Button(main, text="开始升级", command=self.start)
        self.start_button.pack(anchor='w', pady=8)
        ttk.Label(main, textvariable=self.stage).pack(anchor='w')
        self.bars = {}
        for key, label in [('erase', '擦除进度'), ('write', '写入进度')]:
            ttk.Label(main, text=label).pack(anchor='w', pady=(8, 0))
            self.bars[key] = ttk.Progressbar(main, maximum=100)
            self.bars[key].pack(fill='x', pady=4)
        self.result = tk.Label(main, text="升级结果：未开始", anchor='w', fg='#555555')
        self.result.pack(fill='x', pady=10)
        self.log = tk.Text(main, height=5, state='disabled')
        self.log.pack(fill='both', expand=True)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.scan()
        root.after(100, self.pump)

    def note(self, text):
        self.log.config(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.config(state='disabled')

    def scan(self):
        if self.busy:
            return
        try:
            ports = sorted(list_ports.comports(), key=lambda p: (not (p.vid == 0xFFAA and p.pid == 0x5555), p.device))
            self.ports['values'] = [p.device for p in ports]
            if ports and self.ports.get() not in self.ports['values']:
                self.ports.set(ports[0].device)
            if not ports:
                self.ports.set('')
            self.note('扫描：' + ('；'.join(p.device + ' ' + p.description for p in ports) or '未发现串口'))
        except Exception as exc:
            messagebox.showerror('扫描失败', str(exc))

    def disconnect(self):
        if self.port:
            try:
                self.port.close()
            finally:
                self.port = None
        self.open_button.config(text='打开串口')
        self.status.set('串口已关闭')

    def toggle(self):
        if self.busy:
            return
        try:
            if self.port:
                self.disconnect()
                return
            baud = int(self.baud.get())
            if baud <= 0 or not self.ports.get():
                raise ValueError('请选择串口并输入有效波特率')
            self.port = serial.Serial(self.ports.get(), baudrate=baud, timeout=0.1, write_timeout=3)
            self.open_button.config(text='关闭串口')
            self.status.set('已打开 %s，%d baud' % (self.port.port, baud))
        except Exception as exc:
            messagebox.showerror('打开/关闭串口失败', str(exc))

    def choose(self):
        path = filedialog.askopenfilename(filetypes=[('SDK 固件', '*.bin')])
        if path:
            self.firmware.set(path)

    def lock(self, busy):
        self.busy = busy
        for widget in [self.scan_button, self.open_button, self.choose_button, self.start_button, self.baud]:
            widget.config(state='disabled' if busy else 'normal')
        self.ports.config(state='disabled' if busy else 'readonly')

    def start(self):
        if self.busy:
            return
        try:
            if not self.port or not self.port.is_open:
                raise ValueError('请先打开 USB CDC 虚拟串口')
            image = load_firmware(self.firmware.get())
        except Exception as exc:
            messagebox.showerror('无法开始升级', str(exc))
            return
        self.lock(True)
        for bar in self.bars.values():
            bar['value'] = 0
        self.result.config(text='升级结果：升级中', fg='#555555')
        self.note('固件：%s，文件实际长度 %d 字节' % (Path(self.firmware.get()).name, len(image)))
        threading.Thread(target=self.worker, args=(image,), daemon=True).start()

    def worker(self, image):
        try:
            OtaClient(self.port, lambda message: self.events.put(('log', message))).upgrade(image, lambda *args: self.events.put(('progress', args)))
            self.events.put(('success', None))
        except Exception as exc:
            self.events.put(('error', str(exc)))

    def pump(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self.note(value)
                elif kind == 'progress':
                    stage, done, total = value
                    if stage in self.bars:
                        percent = done * 100 / total
                        self.bars[stage]['value'] = percent
                        self.stage.set(('%s：%.1f%% (%d/%d)' % ('擦除' if stage == 'erase' else '写入', percent, done, total)))
                    elif stage == 'crc':
                        self.stage.set('设备 CRC32 校验及镜像提交中…')
                else:
                    self.lock(False)
                    try:
                        self.disconnect()
                    except Exception:
                        self.port = None
                    if kind == 'success':
                        self.stage.set('CRC32 校验通过，已提交镜像并请求设备重启')
                        self.result.config(text='升级成功：CRC32 校验通过', fg='green')
                        self.note('设备已确认镜像提交；重启后的运行状态需连接设备确认。')
                    else:
                        self.stage.set('升级失败，请重新打开串口后重试')
                        self.result.config(text='升级失败', fg='red')
                        self.note(value)
                        messagebox.showerror('升级失败', value)
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def close(self):
        if self.busy:
            messagebox.showinfo('升级中', '请等待升级结束或报错后关闭窗口')
            return
        try:
            self.disconnect()
        finally:
            self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
