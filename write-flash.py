#!/usr/bin/python3
#
# Write Winbond W25N01GV flash chips through Hydrabus

import pyHydrabus
import coloredlogs, logging
import sys
import time
from datetime import timedelta
import os

logger = logging.getLogger("write-flash")
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
	"page_size" : 2048,
	"num_pages" : 65536,
	"pages_per_eraseblock" : 64,
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

def is_busy(hb):
	sr3 = hb.write_read(b"\x0f\xc0",1)
	if sr3[0] & 0b1 == 0:
		return False
	else:
		return True

def erase_chip(hb):
	# turn off block protect bits: set SR1 0xax to 0x00
	sr1 = hb.write_read(b"\x0f\xa0",1)
	logger.debug("sr1 is  " + bin(sr1[0]) + " " + hex(sr1[0]))

	# check if block protect bits already off	
	if (sr1[0] & 0b01111100) == 0:
		logger.debug("block protect bits already 0")
	else:
		# turn off block protect bits
		cmd =  b'\x1f\xa0\x00'
		hb.write(cmd)

	#loop through all the blocks
	num_eraseblocks = int(round(settings["num_pages"] / settings["pages_per_eraseblock"]))

	for block in range(0,num_eraseblocks):
		# wait for busy bit to clear
		while(is_busy(hb)):
			logger.debug("chip Busy")
		
		# execute write enable [ 0x06 ]
		hb.write_read(b"\x06",0)

		# execute block erase [ 0xd8 0x00 16-bit-address ]	
		logger.info("Erasing block " + str(block) + "/" + str(num_eraseblocks))
		block_address = block * 64
		hb.write_read(b"\xd8\x00" + block_address.to_bytes(2,byteorder="big"))

def write_chip(hb, filename):
	# open file

	with open(filename, "rb") as fd:
		for page in range(0, settings["num_pages"]):
			# read 1 page worth of data from file
			data = fd.read(settings["page_size"])
			
			# check if data is not all 0xFF (we can skip)
			if data == (b"\xff" * settings["page_size"]) :
				logger.info("skipping empty page " + str(page))
			
			else:
				logger.info("writing page " + str(page))
				# wait for busy bit to clear
				while(is_busy(hb)):
					logger.debug("chip Busy")
				
				# execute write enable [ 0x06 ]
				hb.write_read(b"\x06",0)
				
				# load program data [ 0x02 16bit_column_address(should be 0x00 0x00) 2048_data ]
				hb.write_read(b"\x02\x00\x00" + data, 0)

				# program execute [0x10 0x00 16bit_page_address ]
				hb.write_read(b"\x10\x00" + page.to_bytes(2,byteorder="big"),0)

if __name__ == '__main__':

	if len(sys.argv) != 2:
		print("Usage: " + sys.argv[0] + " image")
		print("image should be the full size of the chip")
		sys.exit()

	if os.path.getsize(sys.argv[1]) != (settings["num_pages"] * settings["page_size"]):
		print("infile must be full chip size image")
		sys.exit()

	hb = hb_setup()

	# erase whole chip
	start_time = time.monotonic()
	erase_chip(hb)
	erase_time = time.monotonic() - start_time
	

	# write whole chip
	start_time = time.monotonic()
	write_chip(hb,sys.argv[1])
	write_time = time.monotonic() - start_time

	logger.info("erased in " + str(timedelta(seconds=erase_time)) + " | written in " + str(timedelta(seconds=write_time)))
