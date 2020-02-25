# LiteX DMA + CSR tutorial
This is meant a minimal example of how to 
get DMA, CSRs, and interrupts working on the ECP5 FPGA 
and in litex_sim using the litex tools. 

This tutorial should apply fairly well to other LiteX supported
FPGAs...

I need to fix the codebase so that we get the same write order
in both sim and on the FPGA.

## Getting Started
---

To initiate simulation, do: 

```
./sim.py --with-sdram --sdram-module MT41K64M16 --sdram-data-width=16
``` 


To build and program the Versa ECP5 FPGA, do:
```
./versa_ecp5.py build
./versa_ecp5.py load
screen /dev/ttyXXX<ECP5_UART> 115200
#you may have to modify FTDI devices on linux to get screen working
```

## What Currently Happens
---

``yoshimod.py`` is accessing the DRAM through DMA.

Currently, whenever ``1`` is written to the ``yoshimod.py`` CSR, then ``yoshimod`` begins to access DRAM through DMA.

yoshimod writes to address ``0x4`` in simulation, which maps to ``0x40000010`` in in the CPU's address space.

So pay attention to ``0x40000010`` below:

In sim, inspecting ``0x40000000`` to ``0x40000010``, I see:

```
litex> mr 0x40000000 32
Memory dump:
0x40000000  00 00 00 00 01 00 00 00 02 00 00 00 03 00 00 00  ................
0x40000010  05 00 00 00 04 00 00 00 03 00 00 00 02 00 00 00  ................
```

however on the FPGA, I see

```
litex> mr 0x40000000 32
Memory dump:
0x40000000  00 00 00 00 01 00 00 00 02 00 00 00 03 00 00 00  ................
0x40000010  02 00 00 00 03 00 00 00 04 00 00 00 05 00 00 00  ................
```

which means that the data is written backwards in sim from the way it is
on the FPGA...

## Tasks
---

 - [x] Control the amount of bytes written
 
       you HAVE to write X bytes on each ram access where X is the ram interface width

 - [x] Make simulation match FPGA, that is, have both simulation and FPGA write either both 32 bytes or both 16 bytes.

       this is done by passing ``--sdram-data-width=16`` to ``sim.py``

 - [ ] Make write order in sim match that of the FPGA... I have a feeling
this is just a simple setting.