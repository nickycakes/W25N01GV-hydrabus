#!/usr/bin/python3
#
# Dump Winbond W25N01GV flash chips through Hydrabus

import pyHydrabus
import coloredlogs, logging
import sys
import time
from datetime import timedelta

logger = logging.getLogger("dump-flash")
coloredlogs.install(level='INFO')



settings = {
	# SPI1 or SPI2
	# pins:  
	#	SPI1: [CS PA15] [CLK PB3 ] [MISO PB4] [MOSI PB5]
	#	SPI2: [CS PC1 ] [CLK PB10] [MISO PC2] [MOSI PC3]
	"hb_spi" : 1,  # 1 = SPI1, 2 = SPI2
    
	# SPI clock speed 0-7 (slowest to fastest)
	# 	SPI1 320k, 650k, 1.31M, 2.62M, 5.25M, 10.5M, 21M, 42M
	# 	SPI2 160k, 320k, 650k, 1.31M, 2.62M, 5.25M, 10.5M, 21M
	# affects how long it takes to read from chip to hydrabus
	# try reducing if getting bad data 
	"spi_speed" : 7,

	# number of bytes to read from the chip at a time
	# max 4096 (hydrabus buffer size)
	# does not need to be the actual page size of the chip
	"page_size" : 4096,
	"num_pages" : 32768,
}


def hb_setup():
	hb = pyHydrabus.SPI()

	# select SPI1 or SPI2, pyHydrabus seems to default to SPI2 atm
	if settings["hb_spi"] == 2:
		hb.device = 0
	else:
		hb.device = 1

	#should be the defaults
	hb.phase = 0
	hb.polarity = 0

	hb.set_speed(settings["spi_speed"])

	device_id = hb.write_read(b"\x9f\x00",3)
	logger.info("chip ID: " + device_id.hex())
	if device_id != b'\xef\xaa\x21':
		error("chip doesn't seem to be connected properly", hb)

	return(hb)

def error(msg, hb=None):
	logger.error(msg)
	if hb != None:
		hb_cleanup(hb)
	sys.exit()

def hb_cleanup(hb):
	hb.close()


# read status register 2
# write status register 2 with buffer mode bit 0
def set_continuous_mode(hb):
	sr2 = hb.write_read(b"\x0f\xb0",1)
	logger.debug("sr2 is  " + bin(sr2[0]) + " " + str(sr2))
	
	#paranoid check to make sure the reserved bits (should always be 0) are 0
	#sr2 has permanent lock bits that i don't want to accidentally set bc bad data read
	if (sr2[0] & 0b111) != 0:
		error("possible bad data, quit to be safe", hb)

	#check if we're in continuous mode
	if (sr2[0] & 0b1000) == 0:
		logger.debug("already in continuous mode")
	else:
		new_sr2 = sr2[0] - 0b1000
		cmd =  b'\x1f\xb0' + new_sr2.to_bytes(1,byteorder="big")
		hb.write(cmd)

# tell chip to read first page into buffer
# execute continuous read
# read data 1 page at a time, write to file
def dump_continuous(hb, filename):
	#load page 0 into buffer
	page_data_read_cmd = b'\x13\x00\x00\x00'
	hb.write(page_data_read_cmd)

	#set cs low, execute read command
	read_data_cmd = b'\x03\x00\x00\x00'
	hb.cs = 0
	hb.write(read_data_cmd,drive_cs=1)

	#loop through reads from the chip and write data to file
	with open(filename,"wb") as dumpfile:

		start_time = time.monotonic()

		for page_num in range(0,settings["num_pages"]):
			dumpfile.write(hb.write_read(read_len=settings["page_size"],drive_cs=1))
			logger.info("Dumped page " + str(page_num))

		elapsed_time = time.monotonic() - start_time
		data_size = settings["num_pages"] * settings["page_size"]
		transfer_rate = data_size / elapsed_time
		logger.info(str(data_size) + "B in " + str(timedelta(seconds=elapsed_time)) + " ("+ str(round(transfer_rate)) + "B/s)")

	#set cs high when finished
	hb.cs = 1

if __name__ == '__main__':

	if len(sys.argv) != 2:
		print("Usage: " + sys.argv[0] + " outfile")
		sys.exit()


	hb = hb_setup()
	set_continuous_mode(hb)
	dump_continuous(hb,sys.argv[1])