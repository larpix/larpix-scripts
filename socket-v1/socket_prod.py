# run from /home/apdlab/larpixv1/larpix-control-master/larpix-control/larpix/scripts
# after running env3  
# cd ~/larpixv1/larpix-control-master/ ;  source env3/bin/activate
# Socket board chip_ID pins need weaker pullups.  Something like 
# 1 or 2k might work.  0k works. 
# board hard-wired for ID=15.  (bottom 4 bits high, top for low)
# this is not easily changeable. 

import subprocess,sys
import larpix.larpix as larpix
from larpix.larpix import Controller
from larpix.io.zmq_io import ZMQ_IO
from larpix.logger.h5_logger import HDF5Logger
import time
import tkinter as tk
from tkinter import ttk

def init_controller():
	c = Controller()
	c.io = ZMQ_IO('../configs/io/daq-srv1.json', miso_map={2:1})
	c.io.ping()
	return c

def init_board(c):
	#c.load('../configs/controller/pcb-3_chip_info.json')
	c.load('../configs/controller/socket-board-v1.json')
	c.io.ping()

def init_chips(c):
	for chip in c.chips.values(): 
		chip.config.load('../configs/chip/quiet.json')
		chip.config.channel_mask = [1] * 32  # Turn off all channels

	for chip in c.chips.values(): print(chip.config)

	for chip in c.chips.values(): c.write_configuration(chip.chip_key)

	for chip in c.chips.values(): c.verify_configuration(chip.chip_key)

	chip = list(c.chips.values())[0] # selects 1st chip in chain
	#chip = list(c.chips.values())[1] # selects 2nd chip in chain
	#chip = list(c.chips.values())[2] # selects 3rd chip in chain
	#chip = list(c.chips.values())[3] # selects 3rd chip in chain
	chip.chip_key
	print(chip.config)
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)
	return chip

def enable_channel(chan):
	# Configure one channel to be on.
	chip.config.channel_mask = [1] * 32  # Turn off all channels
	chip.config.channel_mask[chan]=0  # turn ON this channel
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)

# Set global threshold
def setGlobalThresh(c,chip,Thresh=50):
	#print(chip.chip_key)	
	#print(id(chip.config))		
	chip.config.global_threshold=Thresh
	c.write_configuration(chip.chip_key)
	#c.verify_configuration(chip.chip_key)

# Turn on a series of channels (a list would be better) on analog
# monitor and loop to the next one every 5 seconds.
def AnalogDisplayLoop(firstChan=0,lastChan=31):
	for chan in range(firstChan,lastChan+1):
		AnalogDisplay(chan)
		time.sleep(5)

# set a really long periodic reset (std=4096, this is 1M)
#chip.config.reset_cycles=1000000

# Turn on and display one channel on analog monitor
def AnalogDisplay(chan):
	# Configure one channel to be on.
	chip.config.channel_mask = [1] * 32  # Turn off all channels
	chip.config.channel_mask[chan]=0  # turn ON this channel
	# Enable analog monitor on one channel at a time	
	c.enable_analog_monitor(chip.chip_key,chan)	
	print("Running Analog mon on channel ",chan)	
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)
	#time.sleep(5) # move to the loop
	#c.disable_analog_monitor(chip.chip_key)

# Loop over approximately all channels and output analog mon for 5 seconds.
#AnalogDisplayLoop(0,31)

# Capture Data for channels in sequence



def ReadChannelLoop(firstChan=0,lastChan=31,monitor=0):
	#sleeptime=0.1
	#c.start_listening()
	for chan in range(firstChan,lastChan+1):
		ReadChannel(chan,monitor)		
		#time.sleep(sleeptime)
	#c.stop_listening()
	chip.config.channel_mask = [1] * 32  # Turn off all channels
	c.write_configuration(chip.chip_key)


def ReadChannel(chan,monitor=0):
	# Configure one channel to be on.
	chip.config.channel_mask = [1] * 32  # Turn off all channels
	chip.config.channel_mask[chan]=0  # turn ON this channel
	if (monitor==1):
		# Enable analog monitor on channel	
		c.enable_analog_monitor(chip.chip_key,chan)	
		print("Running Analog mon for Pulser on channel ",chan)	
	c.write_configuration(chip.chip_key)
	#c.verify_configuration(chip.chip_key)
	loop=0
	looplimit=1
	while loop<looplimit :
		# Read some Data (this also delays a bit)
		c.run(0.1,'test')
		#print(c.reads[-1])
		loop=loop+1	


def get_baseline_selftrigger():
	# Capture Baseline for all channels one by one

	# Turn on periodic_reset
	chip.config.periodic_reset = 1 
	# Reduce global threshold to get baseline data
	chip.config.global_threshold=5 
	# Extend the time for conversion as long as possible
	chip.config.sample_cycles=150
	#chip.config.sample_cycles=1 #(set to default starting 2/21/2020)
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)

	subprocess.run(["rm","testing.h5"])

	#logger declared and switched enabledc.
	c.logger = HDF5Logger("testing.h5", buffer_length=1000000)
	#c.logger = HDF5Logger("testing.h5", buffer_length=10000)
	c.logger.enable()
	c.logger.is_enabled()

	c.verify_configuration(chip.chip_key)
	print(chip.config)

	ReadChannelLoop(0,31,0)

	print("the end")

	c.logger.disable()
	#c.logger.flush()
	c.logger.close()

	import socket_baselines


def get_baseline_periodictrigger(c,chip):
	# Capture Baseline for all channels

	# Turn on periodic_reset
	chip.config.periodic_reset = 1 
	# Reduce global threshold to get baseline data
	chip.config.global_threshold=255 
	# Extend the time for conversion as long as possible
	#chip.config.sample_cycles=255
	chip.config.sample_cycles=1 #(set to default starting 2/21/2020)
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)

	subprocess.run(["rm","testing2.h5"])

	chip.config.channel_mask = [0] * 32  # Turn ON all channels
	chip.config.external_trigger_mask = [0] * 32  # Turn ON all channels
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)
	print(chip.config)

	#logger declared and switched enabledc.
	c.logger = HDF5Logger("testing2.h5", buffer_length=1000000)
	#c.logger = HDF5Logger("testing.h5", buffer_length=10000)
	c.logger.enable()
	c.logger.is_enabled()

	c.run(10,'test')

	print("the end")

	c.logger.disable()
	#c.logger.flush()
	c.logger.close()

	import socket_baselines2


def PulseChannelLoop(firstChan=0,lastChan=31,amp=0,monitor=0):
	for chan in range(firstChan,lastChan+1):
		PulseChannel(chan,amp,monitor)		

def PulseChannel(chan,amp=0,monitor=0):
        # Configure one channel to be on.
        chip.config.channel_mask = [1] * 32  # Turn off all channels
        chip.config.channel_mask[chan]=0  # turn ON this channel
        if (monitor==1):
                # Enable analog monitor on channel
                c.enable_analog_monitor(chip.chip_key,chan)
                print("Running Analog mon for Pulser on channel ",chan)
        c.write_configuration(chip.chip_key)
        #c.verify_configuration(chip.chip_key)
        loop=0
        looplimit=5
        while loop<looplimit :
                c.enable_testpulse(chip.chip_key, [chan], start_dac=200)
                c.issue_testpulse(chip.chip_key, amp, min_dac=100)
                # Read some Data (this also delays a bit)
                #c.run(1,'test')
                print(c.reads[-1])
                loop=loop+1

def get_charge_injection():
	# Run some pulser 

	# Turn on periodic_reset
	chip.config.periodic_reset = 1 
	# Reduce global threshold to get some data
	chip.config.global_threshold=50 
	# Extend the time for conversion as long as possible
	chip.config.sample_cycles=255
	chip.config.channel_mask = [1] * 32  # Turn off all channels
	chip.config.external_trigger_mask = [1] * 32  # Turn OFF ext trig all channels
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)
	PulseChannelLoop(0,31,10,0)


def get_leakage_data():
	# This part is not quite ready yet.
	# Still not ready 20200212 - required thresh values depend on channel 
	# and you only want ot do it on channels that are good so far.

	# Turn off periodic_reset
	chip.config.periodic_reset = 0 # turn off periodic reset
	chip.config.channel_mask = [1] * 32  # Turn off all channels
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)

	for thresh in [25,27,30,35]:
		setGlobalThresh(thresh)
		outfile = "testing" + str(thresh) + ".h5"
		print("Writing ",outfile)
		#logger declared and switched enabledc.
		c.logger = HDF5Logger(outfile, buffer_length=1000000)
		#c.logger = HDF5Logger("testing.h5", buffer_length=10000)
		c.logger.enable()
		c.logger.is_enabled()
		# Configure one channel to be on.
		for chan in range(32):	
			print("running channel ",chan)
			if socket_baselines.mean[chan] > 240 or socket_baselines.sdev[chan] < 2 : continue
			chip.config.channel_mask = [1] * 32  # Turn off all channels
			chip.config.channel_mask[chan]=0  # turn ON this channel
			c.write_configuration(chip.chip_key)
			c.verify_configuration(chip.chip_key)
			# Read some Data (this also delays a bit)
			c.run(1,'test')
			print(c.reads[-1])
			print("the end")
		c.logger.disable()
		#c.logger.flush()
		c.logger.close()

def get_ThreshLevels(c,chip):
	for chan in range(32):	
		print("running channel ",chan)
		chip.config.channel_mask = [1] * 32  # Turn off all channels
		chip.config.channel_mask[chan]=0  # turn ON this channel
		c.write_configuration(chip.chip_key)
		c.verify_configuration(chip.chip_key)
		thresh=128
		step = 16
		rate = 0
		sampleTime = 0.30  # if you use smaller, need to use packet times for better precision
		stepthresh = 10
		while rate < 300 and ( thresh >= 1 and step >= 2 ) :
			setGlobalThresh(c,chip,thresh)
			# Read some Data (this also delays a bit)
			c.run(sampleTime,'test')
			numsamples=len(c.reads[-1])
			# find duration of samples (first/last)
			sampleIter=0
			while sampleIter<numsamples :
				if c.reads[-1].packets[sampleIter].chip_key != None :
					if c.reads[-1].packets[sampleIter].channel_id == chan :
						firstTime = c.reads[-1].packets[sampleIter].timestamp
						sampleIter=numsamples # To end the loop 
						#print("End time at ",numsamples-sampleIter-1)
				sampleIter=sampleIter+1
			sampleIter=0
			while sampleIter<numsamples :
				if c.reads[-1].packets[numsamples-sampleIter-1].chip_key != None :
					if c.reads[-1].packets[numsamples-sampleIter-1].channel_id == chan :
						lastTime = c.reads[-1].packets[numsamples-sampleIter-1].timestamp
						sampleIter=numsamples # to end the loop
						#print("End time at ",numsamples-sampleIter-1)
				sampleIter=sampleIter+1
			dt = lastTime-firstTime 
			if dt < 0 : dt =dt+2**24
			if dt == 0 : dt = dt+sampleTime*5E6
			dt = dt / 5E6
			#print(dt,"<- delta and first time: ",firstTime,"Last time: ",lastTime)
			#rate = numsamples/sampleTime			
			rate = numsamples/dt
			print("Channel ",chan," Thresh ",thresh," Rate ",rate)
			thresh = thresh - step 
			if rate > stepthresh and step > 2 :
				thresh = thresh + step +step
				step = int(step/2)
				if step < 4 : sampleTime=1.0
				if rate < 100 :	stepthresh = stepthresh + stepthresh
		setGlobalThresh(c,chip,255)
		#print("c.reads is ",len(c.reads)," long")
		#print("c.reads is ",sys.getsizeof(c.reads)," long")
		c.reads.clear()
		#print("c.reads is ",len(c.reads)," long")
		#print("c.reads is ",sys.getsizeof(c.reads)," long")
		print("the end")

def RunTests():
	#Not sure how to find the mylabel object
	#window.mybutton.configure(text='Running...')
	#print(window.children)
	# this depends on order buttons are created, I think
	window.children['!frame'].children['!button'].configure(text='Running...')
	# grey out selection boxes
	for myiter in testCheckframe.children:
		# print('disabling ', myiter)
		testCheckframe.children[myiter].state(['disabled'])
		window.update()



	# Update progress boxes along the way
	time.sleep(10)

	# Reenable boxes
	#testCheckframe.state(['!disabled'])
	for myiter in testCheckframe.children:
		# print('disabling ', myiter)
		testCheckframe.children[myiter].state(['!disabled'])
		window.update()

	window.children['!frame'].children['!button'].configure(text='Run Test')


def trygui():
	#window = tk.Tk()
	#global runPeriodicBaseline
	#global runBaseline
	mainframe = ttk.Frame(window, padding="3 3 12 12")
	mainframe.grid(column=0, row=0, sticky=("N, W, E, S"))
	window.columnconfigure(0, weight=1,uniform='a')
	window.rowconfigure(0, weight=1,uniform='a')
	window.title("ASIC Testing Controller")
	window.geometry('+100+100')
	#print("Window is at ",str(window))

	mylabel = ttk.Label(mainframe, text="ASIC testing")
	mylabel.grid(column=0,row=0)
	#print("mylabel is at ",str(mylabel))

	mybutton= ttk.Button(mainframe,text="Run Tests",command=RunTests)
	#mybutton= ttk.Button(window,text="Run PeriodicBaseline")
	#print("mybutton is at ",str(mybutton))
	mybutton.grid(column=0,row=1)

	print("trygui")

	mychipIDBox = []
	def deploySN():
		if int(numChipVar.get()) > len(mychipIDBox):
			for ChipNum in range(len(mychipIDBox)+1,int(numChipVar.get())+1):
				print(ChipNum)
				mychipIDBox.append(ttk.Entry(SNframe,width=6))
				mychipIDBox[ChipNum-1].grid(column=4,row=ChipNum,sticky='E') 
		if int(numChipVar.get()) < len(mychipIDBox):
			for ChipNum in range(len(mychipIDBox),int(numChipVar.get()),-1):
				print(ChipNum)
				mychipIDBox[ChipNum-1].state(['disabled'])
		for ChipNum in range(1,int(numChipVar.get())+1):
			mychipIDBox[ChipNum-1].state(['!disabled'])


#	print(runPeriodicBaseline.get()," = runPeriodicBaseline")
#	PerBaselineButton = ttk.Checkbutton(mainframe,text=
#		"Run PerBaseline",variable=runPeriodicBaseline,command=printStatus,onvalue="1",offvalue="0")
#	runPeriodicBaseline.set("1")
#	print(runPeriodicBaseline.get()," = runPeriodicBaseline")
#	runPeriodicBaseline.set("0")
#	print(runPeriodicBaseline.get()," = runPeriodicBaseline")
#	runPeriodicBaseline.set("1")
#	print(runPeriodicBaseline.get()," = runPeriodicBaseline")
#	#PerBaselineButton.state=runPeriodicBaseline
#	PerBaselineButton.grid(column=0,row=3,sticky="W")

#	print(runBaseline.get()," = runBaseline")
#	BaselineButton = ttk.Checkbutton(mainframe,text="Run Baseline",variable=runBaseline,command=printStatus)
#	#runBaseline=0
#	#BaselineButton.value=0 #runBaseline
#	BaselineButton.grid(column=0,row=4,sticky="W")

	global testList
	testList = ["Periodic Baseline",
			"Baseline",
			"Thresh Levels",
			"Leakage Data",
			"Charge Injection",
			"Pulse Data",
			"Analog Display"]
	testDefaults = [1,0,1,0,1,0,1]
	testFunctionNames = ["get_baseline_periodictrigger",
				"get_baseline_selftrigger",
				"get_ThreshLevels",
				"get_leakage_data",
				"get_charge_injection",
				"PulseChannelLoop",
				"AnalogDisplayLoop"]
	testFunctions = [] 

	global buttonVars
	#buttonVars = [] #[len(testList)] # will hold StringVar()
	testButton = [] #[len(testList)] # will hold test checkbuttons

	testID=0
	print(len(testList))
	global testCheckframe 
	testCheckframe = ttk.Frame(mainframe,padding="3 3 12 12")
	testCheckframe.grid(column=0,row=5)
	row=0	
	for test in testList:
		testFunctions.append(testFunctionNames[testID])
		print(test)
		buttonVars.append(tk.StringVar())
		buttonVars[testID].set(testDefaults[testID])
		testButton.append(ttk.Checkbutton(testCheckframe,
			text=test,variable=buttonVars[testID],command=printStatus))
		testButton[testID].grid(column=0,row=row,sticky="W")
		row = row+1
		testID=testID+1

#	print(runBaseline.get()," = runBaseline")
#	BaselineButton = ttk.Checkbutton(mainframe,text="Run Baseline",variable=runBaseline,command=printStatus)
#	BaselineButton.grid(column=0,row=5,sticky="W")

	textBox=tk.Text(mainframe, width = 40, height=10)
	textBox.grid(column=9,row=2,rowspan=10)

	closebutton= ttk.Button(mainframe,text="Quit",command=window.destroy)
	closebutton.grid(column=9,row=99,sticky='E')
	#print("closebutton is at ",str(closebutton))

	SNframe = ttk.Frame(mainframe, padding="3 3 12 12")
	SNframe.grid(column=9,row=0,rowspan=2,sticky='E')
	SNlabel = ttk.Label(SNframe, text="ASICs to test (1-10)")
	SNlabel.grid(column=1,row=0)
	numChipVar = tk.StringVar()
	#numChipVar.set("2")
	numChipWheel = tk.Spinbox(SNframe,from_=1,to=10,textvariable=numChipVar,command=deploySN)
	numChipWheel.grid(column=1,row=1,sticky='W')
	# this makes it interactive?
	window.mainloop()
	

def mainish():

	trygui()
	
	exit()
	
	c=init_controller()
	init_board(c)
	chip=init_chips(c)	
	print(chip)	
	
	# Set global threshold
	setGlobalThresh(c,chip,50)

	# Read some Data
	#c.run(1,'test')
	#print(c.reads[-1])

	# Enable analog monitor on one channel
	c.enable_analog_monitor(chip.chip_key,28)
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)

	# Turn on periodic_reset
	chip.config.periodic_reset = 1 # turn on periodic reset
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)

	# Turn off periodic_reset
	chip.config.periodic_reset = 0 # turn off periodic reset
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)

	# Disable analog monitor (any channel)
	c.disable_analog_monitor(chip.chip_key)
	c.write_configuration(chip.chip_key)
	c.verify_configuration(chip.chip_key)

	#get_baseline_periodictrigger(c,chip)
	get_ThreshLevels(c,chip)

def printStatus():
#	global runPeriodicBaseline
#	global runBaseline
	print("printStatus")
	#print(runPeriodicBaseline.get()," = runPeriodicBaseline")
	# runPeriodicBaseline.set("0")
	# print(runPeriodicBaseline.get()," = runPeriodicBaseline")
	#runPeriodicBaseline.set("1")
	#print(runPeriodicBaseline.get()," = runPeriodicBaseline")
	#print(runBaseline.get()," = runBaseline")
	myiter = 0
	for i in buttonVars:
		print(buttonVars[myiter].get()," = ",testList[myiter])
		myiter=myiter+1

# make the controlling window global. (will probably need a better name)
window = tk.Tk()
#runPeriodicBaseline = tk.StringVar()
#runBaseline = tk.StringVar()
#runPeriodicBaseline.set("1")
#runBaseline.set("0")

testList = []
buttonVars = []
testCheckfram = []

#runPeriodicBaseline="1"
#runBaseline="0"
mainish()

