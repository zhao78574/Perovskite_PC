import pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy.stats import gaussian_kde
from matplotlib.ticker import MultipleLocator
p='/mnt/data/筛选程序_示例结果_四组各16个.xlsx'
df=pd.read_excel(p,sheet_name='入选数据')
groups=['最差','差','良','优']; labels=['Worst','Poor','Good','Best']
colors=['#a7a7a7','#3e9dd5','#f0a53c','#f04b55']
metrics=[('PCE (%)','PCE (%)'),('Voc (V)',r'$V_{OC}$ (V)'),('Jsc (mA/cm²)',r'$J_{SC}$ (mA cm$^{-2}$)'),('FF','FF (%)')]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.linewidth':0.85,'pdf.fonttype':42,'ps.fonttype':42})
fig,axs=plt.subplots(2,2,figsize=(10.2,4.7)); rng=np.random.default_rng(7)
for ax,(col,ylabel) in zip(axs.flat,metrics):
 for i,(g,color) in enumerate(zip(groups,colors),1):
  v=df.loc[df['筛选组别']==g,col].dropna().astype(float).to_numpy()
  q1,med,q3=np.percentile(v,[25,50,75]); low,high=v.min(),v.max()
  ax.add_patch(Rectangle((i-.25,q1),.37,q3-q1,facecolor=color,edgecolor=color,alpha=.6,lw=.9))
  ax.plot([i-.25,i+.12],[med,med],color=color,lw=1.4)
  ax.plot([i-.07,i-.07],[low,q1],color=color,lw=.8)
  ax.plot([i-.07,i-.07],[q3,high],color=color,lw=.8)
  ax.plot([i-.17,i+.03],[low,low],color=color,lw=.8)
  ax.plot([i-.17,i+.03],[high,high],color=color,lw=.8)
  xx=i-.10+rng.uniform(-.13,.16,len(v))
  ax.scatter(xx,v,s=9,facecolor=color,edgecolor='white',linewidth=.28,zorder=4)
 ax.set_xlim(.55,4.55);ax.set_xticks(range(1,5),labels,fontweight='bold')
 ax.set_ylabel(ylabel,fontweight='bold',fontsize=11)
 ax.tick_params(axis='both',direction='out',length=3,pad=3)
 ax.grid(False)
 vals=df[col].astype(float); spread=vals.max()-vals.min(); ax.set_ylim(vals.min()-spread*.12,vals.max()+spread*.13)
 for spine in ax.spines.values(): spine.set_linewidth(.85)
fig.subplots_adjust(left=.09,right=.985,bottom=.11,top=.97,wspace=.27,hspace=.35)
for ext in ['png','pdf','svg']:
 out=f'/mnt/data/四组性能_纯箱线散点图.{ext}'
 fig.savefig(out,dpi=400,facecolor='white',bbox_inches='tight')
 print(out)
