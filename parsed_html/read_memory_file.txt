COMMAND: read_memory_file

TITLE:
read_memory_files

DESCRIPTION:
Use this command to load a RAM or ROM instance with a memory image.

SYNTAX:
read_memory_file < id | instance_name > file_name [-binary | -hex] [-range first_address last_address]

OPTIONS:
id | instance_name : Specifies the RAM or ROM memory gate for which the memory image file is to be read. It
            is specified by either its primitive ID or its instance pathname
file_name : Indicates the pathname to a file containing the memory contents that are to be read.
            The memory contents must be in Verilog format.
-binary | -hex : Indicates the format of the memory image file. The default is -hex .
-range first_address last_address : Indicates the range for the memory words to be loaded. Specify the first and last
            address in decimal. The default is to load the entire memory.

EXAMPLES:
DRC> read_memory i007/u1/mem/rom1/rom_core i007.d3 -hex
 DRC> report_memory -all
 type   ID    instance_path                   memory_file
 ---- ------- ------------------------------- ---------------
 ROM   5425   i007/u1/mem/rom1/rom_core       i007.d3

