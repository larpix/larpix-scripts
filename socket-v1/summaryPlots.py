
import pandas as pd
import h5py
import plotly
import plotly.express as px
import chart_studio
import chart_studio.plotly as py
import plotly.graph_objs as go
import csv
import numpy as np
from collections import Counter

#varlist = []
#for chan in range(0,32): varlist.append('ch{:02d}'.format(chan))

#meandf = pd.read_csv("20200131_all78/means.csv")
#stddf = pd.read_csv("20200131_all78/sdevs.csv")
#nentdf = pd.read_csv("20200131_all78/nents.csv")
#meandf.plot.hist()
#fig = px.histogram(sdev)
#fig = px.histogram(stddf)
#fig.show()
#fig = px.histogram(stddf,x='ch00')
#fig.show()
#fig = px.histogram(meandf,x='ch00')
#fig.show()

#fig4 = go.Figure()
#for graph in varlist: fig4.add_trace(go.Histogram(x=nentdf[graph]))

#fig4.show()

#fig5 = px.scatter(x=meandf[],y=stddf[])
#fig3.update_layout(barmode="stack")
#fig3.update_layout(barmode="overlay")
#for graph in varlist: fig3.add_trace(go.Histogram(x=meandf[graph],xbins=dict(start=0,end=255,size=3)))

#fig3.show()

# reshape separate csvs to single summary.csv

#summaryFrame = pd.DataFrame(columns = ['runtime','Mean','Std','Nent','ChanName','Chan'])
#summaryFrame2 = pd.read_csv("20200204_tray1_summary.csv")
#summaryFrame = pd.read_csv("20200131_all78/summary.csv")
summaryFrame = pd.read_csv("20200204_tray0_summary.csv")
summaryFrame = pd.read_csv("20200206_boiling_pixel.csv")
#summaryFrame2.tRow = summaryFrame2.tRow-12
# adjust second set to have runtimes after the first + 60 seconds
#lasttime=summaryFrame['runtime'][len(summaryFrame.runtime)-1]
#lasttime
#firsttime2=summaryFrame2['runtime'][0]
#firsttime2
#summaryFrame2.runtime=summaryFrame2.runtime-firsttime2+lasttime+60  
#summaryFrame = summaryFrame.append(summaryFrame2,ignore_index=True)
#numrows = len(meandf['ch00'])
#for row in range(0,numrows):
#	for chan in range(0,32):
#		textchan = 'ch{:02d}'.format(chan) 
#		summaryFrame = summaryFrame.append({'runtime':meandf['runtime'][row],'Mean':meandf[textchan][row],'Std':stddf[textchan][row],'Nent':nentdf[textchan][row],'ChanName':textchan,'Chan':chan},ignore_index=True)

#mydf = pd.concat([pd.DataFrame([meandf['runtime'][row],meandf[textchan][row],stddf[textchan][row],nentdf[textchan][row],textchan,chan],columns = ['runtime','Mean','Std','Nent','ChanName','Chan']) for chan in range(32)],ignore_index=True)

#fig2 = go.Figure()
#for graph in varlist: fig2.add_trace(go.Histogram(x=stddf[graph],xbins=dict(start=0,end=255,size=1)))

fig2 = px.histogram(x=summaryFrame['Mean'],color=summaryFrame['ChanName'])
fig2.update_layout(barmode="stack",xaxis_title="Baseline Mean (ADC)")
fig2.show()
plotly.offline.plot(fig2,filename="Meanstack_bp.html",auto_open=False )

fig3 = px.histogram(x=summaryFrame['Std'],color=summaryFrame['ChanName'])
fig3.update_layout(barmode="stack",xaxis_title="Std Deviation (ADC)")
#fig3.show()
plotly.offline.plot(fig3,filename="Stdstack_bp.html",auto_open=False )

fig5 = px.scatter(x=summaryFrame['Mean'],y=summaryFrame['Std'],color=summaryFrame['ChanName'])
fig5.update_layout(xaxis_title="Baseline Mean (ADC)",yaxis_title="Std Dev (ADC)")
#fig5.show()
plotly.offline.plot(fig5,filename="StdvsMean_bp.html",auto_open=False )

fig6 = px.scatter(x=summaryFrame['runtime']-summaryFrame['runtime'][0],y=summaryFrame['Std'],color=summaryFrame['ChanName'])
fig6.update_layout(xaxis_title="Run Time(s)",yaxis_title="Std Dev (ADC)")
#fig6.show()
#plotly.offline.plot(fig6,filename="StdvsRuntime.html",auto_open=False )

fig7 = px.scatter(x=summaryFrame['runtime']-summaryFrame['runtime'][0],y=summaryFrame['Mean'],color=summaryFrame['ChanName'])
fig7.update_layout(xaxis_title="Run Time(s)",yaxis_title="Baseline Mean (ADC)")
#fig7.show()
#plotly.offline.plot(fig7,filename="MeanvsRuntime.html",auto_open=False )

badChan = summaryFrame[(summaryFrame['Std']<2) | (summaryFrame['Mean']>240)]
badChan.reset_index(drop=True)

fig8 = go.Figure()
fig8.add_trace(go.Histogram(x=badChan['Tray']*90+6*badChan['tRow']+badChan['tColumn'],xbins=dict(size=1)))
fig8.update_layout(xaxis_title="ChipID=Tray*90+row*6+column",yaxis_title="Number Bad Channels")
#fig8.show()
plotly.offline.plot(fig8,filename="BadChanvsChip_bp.html",auto_open=False )

fig9 = px.scatter(x=summaryFrame['Tray']*90+6*summaryFrame['tRow']+summaryFrame['tColumn'],y=summaryFrame['Std'],color=summaryFrame['ChanName'])
fig9.update_layout(xaxis_title="ChipID=Tray*90+row*6+column",yaxis_title="Std Dev (ADC)")
#fig9.show()
plotly.offline.plot(fig9,filename="StdvsChip_bp.html",auto_open=False )

fig10 = px.scatter(x=summaryFrame['Tray']*90+6*summaryFrame['tRow']+summaryFrame['tColumn'],y=summaryFrame['Mean'],color=summaryFrame['ChanName'])
fig10.update_layout(xaxis_title="ChipID=Tray*90+row*6+column",yaxis_title="Baseline Mean (ADC)")
#fig10.show()
plotly.offline.plot(fig10,filename="MeanvsChip_bp.html",auto_open=False )
