#!/usr/bin/env python3

# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018-2019 David Shah <dave@ds0.me>
# License: BSD

import shutil
import os
import litex.soc.integration.builder as builder
import logging

#it's really tricky to modify the litex module source and makefiles at this point 
#In order to add support for a local ./main.c - so I just hack it in there
src = 'main.c'
dest = os.path.join(os.path.dirname(builder.__file__), '..', 'software', 'bios', 'main.c')
temp_dest = os.path.join(os.path.dirname(builder.__file__), '..', 'software', 'bios', '~main.c')

def replace():
    print(dest)
    shutil.copyfile(dest, temp_dest)
    shutil.copyfile(src, dest)

def restore():
    shutil.copyfile(temp_dest, dest)
    os.remove(temp_dest)


import argparse

from migen import *
import sys
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.boards.platforms import versa_ecp5

from litex.build.lattice.trellis import trellis_args, trellis_argdict

from litex.soc.cores.clock import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import MT41K64M16
from litedram.phy import ECP5DDRPHY

from liteeth.phy.ecp5rgmii import LiteEthPHYRGMII
from liteeth.mac import LiteEthMAC

from yoshimod import YoshiMod
from copy_src import Copy_Src

_char_offset = 48

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_init = ClockDomain()
        self.clock_domains.cd_por = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys2x = ClockDomain()
        self.clock_domains.cd_sys2x_i = ClockDomain(reset_less=True)

        # # #

        self.cd_init.clk.attr.add("keep")
        self.cd_por.clk.attr.add("keep")
        self.cd_sys.clk.attr.add("keep")
        self.cd_sys2x.clk.attr.add("keep")
        self.cd_sys2x_i.clk.attr.add("keep")

        self.stop = Signal()

        # clk / rst
        clk100 = platform.request("clk100")
        rst_n = platform.request("rst_n")
        platform.add_period_constraint(clk100, 1e9/100e6)

        # power on reset
        por_count = Signal(16, reset=2**16-1)
        por_done = Signal()
        self.comb += self.cd_por.clk.eq(ClockSignal())
        self.comb += por_done.eq(por_count == 0)
        self.sync.por += If(~por_done, por_count.eq(por_count - 1))

        # pll
        self.submodules.pll = pll = ECP5PLL()
        pll.register_clkin(clk100, 100e6)
        pll.create_clkout(self.cd_sys2x_i, 2*sys_clk_freq)
        pll.create_clkout(self.cd_init, 25e6)
        self.specials += [
            Instance("ECLKSYNCB",
                i_ECLKI=self.cd_sys2x_i.clk,
                i_STOP=self.stop,
                o_ECLKO=self.cd_sys2x.clk),
            Instance("CLKDIVF",
                p_DIV="2.0",
                i_ALIGNWD=0,
                i_CLKI=self.cd_sys2x.clk,
                i_RST=self.cd_sys2x.rst,
                o_CDIVX=self.cd_sys.clk),
            AsyncResetSynchronizer(self.cd_init, ~por_done | ~pll.locked | ~rst_n),
            AsyncResetSynchronizer(self.cd_sys, ~por_done | ~pll.locked | ~rst_n)
        ]

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCSDRAM):
    def __init__(self, sys_clk_freq=int(75e6), toolchain="trellis", **kwargs): 
        platform = versa_ecp5.Platform(toolchain=toolchain)
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
                          l2_size=8192,
                          ident="UDP",
						  uart_baudrate=115200,
                          integrated_rom_size=0x10000,
						  #cpu_type="picorv32",
                          **kwargs)

        # crg
        crg = _CRG(platform, sys_clk_freq)
        self.submodules.crg = crg

        # sdram
        self.submodules.ddrphy = ECP5DDRPHY(
            platform.request("ddram"),
            sys_clk_freq=sys_clk_freq)
        self.add_csr("ddrphy")
        self.add_constant("ECP5DDRPHY", None)
        self.comb += crg.stop.eq(self.ddrphy.init.stop)
        sdram_module = MT41K64M16(sys_clk_freq, "1:2")
        self.register_sdram(self.ddrphy,
            sdram_module.geom_settings,
            sdram_module.timing_settings)
        
        #add yoshi module and connect to DDR
        port = self.sdram.crossbar.get_port(mode="write", dw=32)
        self.submodules.yoshi = yoshi = YoshiMod(port)
        self.add_csr("yoshi")
        self.add_interrupt("yoshi")
        #done 

		
# EthernetSoC --------------------------------------------------------------------------------------

class EthernetSoC(BaseSoC):
    mem_map = {
        "ethmac": 0xb0000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, toolchain="trellis", **kwargs):
        BaseSoC.__init__(self, toolchain=toolchain, integrated_rom_size=0x10000, **kwargs)

        self.submodules.ethphy = LiteEthPHYRGMII(
            self.platform.request("eth_clocks"),
            self.platform.request("eth"))
        self.add_csr("ethphy")
        self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=32,
            interface="wishbone", endianness=self.cpu.endianness)
        self.add_wb_slave(self.mem_map["ethmac"], self.ethmac.bus, 0x2000)
        self.add_memory_region("ethmac", self.mem_map["ethmac"], 0x2000, type="io")
        self.add_csr("ethmac")
        self.add_interrupt("ethmac")

        self.ethphy.crg.cd_eth_rx.clk.attr.add("keep")
        self.ethphy.crg.cd_eth_tx.clk.attr.add("keep")
        self.platform.add_period_constraint(self.ethphy.crg.cd_eth_rx.clk, 1e9/125e6)
        self.platform.add_period_constraint(self.ethphy.crg.cd_eth_tx.clk, 1e9/125e6)

# Load ---------------------------------------------------------------------------------------------
def load():
	import os
	f = open("ecp5-versa5g.cfg", "w")
	f.write(
"""
interface ftdi
ftdi_vid_pid 0x0403 0x6010
ftdi_channel 0
ftdi_layout_init 0xfff8 0xfffb
reset_config none
adapter_khz 25000
jtag newtap ecp5 tap -irlen 8 -expected-id 0x81112043
""")
	f.close()
	os.system("openocd -f ecp5-versa5g.cfg -c \"transport select jtag; init; svf build/gateware/top.svf; exit\"")

# Build --------------------------------------------------------------------------------------------

def main():
	if "load" in sys.argv[1:]:
		load()
		exit()
	if "build" in sys.argv[1:]:
		soc = BaseSoC()
		builder = Builder(soc, output_dir="build", csr_csv="tools/csr.csv")
		vns = builder.build()
	else:
		print("Usage:")
		print("./versa_ecp5.py build")
		print("./versa_ecp5.py load")

if __name__ == "__main__":
    #safely modify the bios with local sources
    #undo changes when done
    with Copy_Src() as context:
        main()