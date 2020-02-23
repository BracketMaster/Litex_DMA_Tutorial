import shutil
import os
import litex.soc.integration.builder as builder


class Copy_Src():
    def __init__(self):
        #it's really tricky to modify the litex module source and makefiles at this point 
        #In order to add support for a local ./main.c etc, - so I just hack it in there
        self.rootDir = '.'
        self.restorables_dict = {}
        self.deletables_list = []
        self.src_ = ['yoshi.c', 'yoshi.h', 'main.c', 'Makefile', 'isr.c']
        self.src_rootDir = os.path.join(
                        os.path.dirname(builder.__file__),
                        '..',
                        'software'
                        )

    def __enter__(self):
        os.chdir('src')

        for dirName, subdirList, fileList in os.walk(self.rootDir):
            for fname in fileList:
                if fname in self.src_:
                    src = f'{dirName}/{fname}'
                    dest = f'{self.src_rootDir}/{dirName}/{fname}'
                    dest_backup = f'{self.src_rootDir}/{dirName}/~{fname}'

                    #perhaps we wish to copy in a local src
                    #that does not exist remotely
                    if os.path.exists(dest):
                        shutil.copyfile(dest, dest_backup)
                        self.restorables_dict.update({dest : dest_backup})

                    #otherwise, its something we can delete later
                    else:
                        self.deletables_list += [dest]
                        
                    shutil.copyfile(src, dest)
        os.chdir('..')

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir('src')
        
        #[print(el) for el in self.deletables_list]

        #restore files the we temporarily replaced from earlier
        for restore,temp in self.restorables_dict.items():
            shutil.copyfile(temp, restore)
            os.remove(temp)

        #delete files that weren't in the Litex source originally
        [os.remove(file) for file in self.deletables_list]
        os.chdir('..')
