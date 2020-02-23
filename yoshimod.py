#from migen import Module, Signal, If, Replicate
from litex.soc.interconnect.csr import AutoCSR, CSRStorage
from litex.soc.interconnect.csr_eventmanager import EventManager, EventSourceProcess
from migen import *
from litedram.frontend.dma import LiteDRAMDMAWriter, LiteDRAMDMAReader


class YoshiMod(Module, AutoCSR):
    def __init__(self, port):
        print(port.__dict__)
        print(port.rdata.__dict__)
        print(port.cmd.__dict__)
        self.port = port
        rdy = Signal(reset=1)
        rdy2 = Signal(reset=1)

        #try using DMA engine

        #debugging
        test_CSRs_and_IRQs = False
        count = Signal(32,reset=0)
        self.sync += count.eq(count + 1)

        # This initializes the hardware for raising an IRQ

        self.submodules.ev = EventManager()
        self.ev.my_irq = EventSourceProcess()
        self.ev.finalize()

        # This initializes a CSR that gets automatically assigned an
        # address. This gets written to in sdram.c when it's finished
        # initializing the ram
        self.sdram_initialized = CSRStorage(size=32)
        self.sd_ram_init = Signal(reset=1)

        #I would set sdram_initialized.storage directly in the FSM,
        #but yosys doesn't like the verilog migen generates when I do
        #that
        #This also synchronously clears the interrupt

        if not test_CSRs_and_IRQs:
            self.sync += \
                If(self.sdram_initialized.storage,
                    self.sdram_initialized.storage.eq(self.sd_ram_init),
                )

        # The ram interface works like so:
        # You must initially send it a command (I used "write") in
        # order for command_ready to go high. Then you can send it a
        # command (read/write), and when it is ready to accept or give
        # data, then the ready signal on the read or write port will
        # go high. So to do a write, I put an address and read/write
        # flag into the command payload field and set its valid
        # flag. I also will put some data onto the wdata payload and
        # set the valid flag for it. Then when I receive a ready
        # signal on wdata.ready, I can clear the valid flag and remove
        # the data.

        #This works in simulation, AND ON the FPGA!!!
        #The FPGA goes through the state machine and prints
        #"hello", but ``mr 0x40000000`` is unchanged.
        count = Signal(8)


        if not test_CSRs_and_IRQs:

            self.submodules.dma = dma = LiteDRAMDMAWriter(port, 5, True)
            self.comb += dma.sink.address.eq(0x00_00_00_00)
            #dma.add_csr()

            self.submodules.fsm = fsm = FSM(reset_state="IDLE")
            fsm.act("IDLE",
                self.ev.my_irq.trigger.eq(0),
                dma.sink.valid.eq(0),
                NextValue(count, 0),

                If(self.sdram_initialized.storage & dma.sink.ready,
                NextState("WRITE_CMD"),
                ),
            )
            fsm.act("WRITE_CMD",
                self.sd_ram_init.eq(0),
                self.ev.my_irq.trigger.eq(1),

                dma.sink.valid.eq(1),
                dma.sink.data.eq(0x89_0A_BC_DE + count),
                NextValue(count, count + 1),


                If((port.wdata.ready == 1) & (count == 3),
                NextState("IDLE"),
                ),
            )

        # This triggers the IRQ on any sdram write. The IRQ is
        # triggered on a falling edge, and conveniently this signal
        # pulses so it works both inverted and not. The IRQ is handled
        # in irq.c/yoshi.c. The interrupt must also be enabled, and
        # that's handled in isr.c         

        #this works on the FPGA
        if test_CSRs_and_IRQs:
            self.sync += \
            If((self.sdram_initialized.storage == 1),
                self.sdram_initialized.storage.eq(count),
                self.ev.my_irq.trigger.eq(1)
            ).Else(
                self.sdram_initialized.storage.eq(count),
                self.ev.my_irq.trigger.eq(0)
            )