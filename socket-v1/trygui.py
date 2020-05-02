import tkinter as tk
from tkinter import ttk

def RunTests():
#	#Not sure how to find the mylabel object
	#window.mybutton.configure(text='Running...')
	#print(window.children)
	# this depends on order buttons are created, I think
	window.children['!frame'].children['!button'].configure(text='Running...')
	# grey out selection boxes
	
	# Get selections and run configured tests

	# Update progress boxes along the way

	# Reenable boxes


def trygui():
	#window = tk.Tk()
	global runPeriodicBaseline
	global runBaseline
	mainframe = ttk.Frame(window, padding="3 3 12 12")
	mainframe.grid(column=0, row=0, sticky=("N, W, E, S"))
	window.columnconfigure(0, weight=1,uniform='a')
	window.rowconfigure(0, weight=1,uniform='a')
	window.title("Here is your GUI window")
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
	
	row=4	
	testID=0
	print(len(testList))
	for test in testList:
		testFunctions.append(testFunctionNames[testID])
		print(test)
		buttonVars.append(tk.StringVar())
		buttonVars[testID].set(testDefaults[testID])
		testButton.append(ttk.Checkbutton(mainframe,
			text=test,variable=buttonVars[testID],command=printStatus))
		testButton[testID].grid(column=0,row=row+1,sticky="W")
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
	#runPeriodicBaseline.set("0")
	#print(runPeriodicBaseline.get()," = runPeriodicBaseline")
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

#runPeriodicBaseline="1"
#runBaseline="0"
mainish()

