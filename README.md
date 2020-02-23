# Getting Started
To initiate simulation, do: 

```
./sim.py --with-sdram --sdram-module MT41K64M16
``` 


To build and program the Versa ECP5 FPGA, do:
```
./versa_ecp5.py build
./versa_ecp5.py load
```

I'm trying to generate a minimal example of how to 
get DMA working on the ECP5 FPGA.

``yoshimod.py`` is accessing the DRAM through DMA.

Currently, whenever ``1`` is written to the ``yoshimod.py`` CSR, then ``yoshimod`` begins to access DRAM through DMA.

In sim, inspecting ``0x40000000``, I see:

```
litex> mr 0x40000000 32
Memory dump:
0x40000000  de bc 0a 89 df bc 0a 89 e0 bc 0a 89 e1 bc 0a 89  ................
0x40000010  de bc 0a 89 df bc 0a 89 e0 bc 0a 89 e1 bc 0a 89  ................

```

While on the actual FPGA, inspecting ``0x40000000``, I see:

```
litex> mr 0x40000000 32
Memory dump:
0x40000000  de bc 0a 89 df bc 0a 89 e0 bc 0a 89 e1 bc 0a 89  ................
0x40000010  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 89  ................

```

## Tasks

 - [ ] Control the amount of bytes written
 - [ ] Find signal that lets me know when to stop writing instead of relying on count == 3.
 - [ ] Make simulation match FPGA, that is, have both simulation and FPGA write either both 32 bytes or both 16 bytes.