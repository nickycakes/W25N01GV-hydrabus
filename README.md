# W25N01GV tools for Hydrabus

Python scripts to interface with W25N01GV nand flash through Hydrabus

Tested on Hydrabus hardware v1.0 rev 4 with hydrafw 1.0

## Installation


```bash
pip3 install -r requirements.txt
```

## Usage

```bash
# dumps entire flash
./dump-flash.py fulldump.bin
```

```bash
# write entire flash with image.bin
./write-flash.py image.bin
```

## Notes

* Make sure all leads are connected properly, 
  * especially HOLD to 3.3v
  * under default settings, write protect pin should not matter for writing
* This script is unlikely to work for other nand flash without heavy modification