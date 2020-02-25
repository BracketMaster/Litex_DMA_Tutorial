#from migen import Module, Signal, If, Replicate
from litex.soc.interconnect.csr import AutoCSR, CSRStorage
from litex.soc.interconnect.csr_eventmanager import EventManager, EventSourceProcess
from migen import *
from litedram.frontend.dma import LiteDRAMDMAWriter, LiteDRAMDMAReader


#try using DMA engine
class YoshiMod(Module, AutoCSR):
    def __init__(self, port):
        print(port.__dict__)
        print(port.rdata.__dict__)
        print(port.cmd.__dict__)
        self.port = port

        # This initializes the hardware for raising an IRQ
        self.submodules.ev = EventManager()
        self.ev.my_irq = EventSourceProcess()
        self.ev.finalize()

        # This initializes a CSR that gets automatically assigned an
        # address. This gets written to in sdram.c when it's finished
        # initializing the ram
        self.sdram_initialized = CSRStorage(size=32)
        self.sd_ram_init = Signal(reset=1)

        #how many times has interrupt been called?
        #this value also gets written to Ram
        interrupt_count = Signal(32)

        #I would set sdram_initialized.storage directly in the FSM,
        #but yosys doesn't like the verilog migen generates when I do
        #that
        #This also synchronously clears the interrupt
        self.sync += \
            If(self.sdram_initialized.storage,
                self.sdram_initialized.storage.eq(self.sd_ram_init),
            )

        #You MUST write an entire DRAM line. Since the DMA frontend
        #in yoshimod is instantiated with a width of 32bits and the 
        #DRAM with on the VERSA SOC is 128 bits, you must do 4 
        #consecutive writes in the "WRITE_CMD" stage.
        #A counter, words_written keeps track of how many words have
        #already been written.
        #Once 4 words have been written, the FSM goes back to idle,
        #toggling the trigger, activating yoshi_interrupt on the CPU,
        #which causes the CPU to print "hello".
        #During each cycle of the counter, whatever is on dma.sink.data
        #gets written to ram.

        words_written = Signal(8)

        self.submodules.dma = dma = LiteDRAMDMAWriter(port, 5, True)
        self.comb += dma.sink.address.eq(0x00_00_00_04)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            self.ev.my_irq.trigger.eq(0),
            dma.sink.valid.eq(0),
            NextValue(words_written, 0),

            If(self.sdram_initialized.storage & dma.sink.ready,
                NextValue(interrupt_count, interrupt_count + 1),
                NextState("WRITE_CMD"),
            ),
        )
        fsm.act("WRITE_CMD",
            self.sd_ram_init.eq(0),
            self.ev.my_irq.trigger.eq(1),

            dma.sink.valid.eq(1),
            dma.sink.data.eq(words_written + interrupt_count),


            If((port.wdata.ready == 1) ,
                If((words_written == 3),
                    NextState("IDLE"),
                ).Else(
                    NextValue(words_written, words_written + 1),
                ),
            ),
        )