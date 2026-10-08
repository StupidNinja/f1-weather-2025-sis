"""Descriptive analysis and labeled plots; no causal or independent-hour inference."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

DAILY_VARS=['temperature_mean_c','relative_humidity_mean_pct','precipitation_total_mm','wind_speed_mean_kmh']
LABELS={'temperature_mean_c':'Temperature mean (°C)','relative_humidity_mean_pct':'Humidity mean (%)',
        'precipitation_total_mm':'Precipitation total (mm)','wind_speed_mean_kmh':'Wind mean (km/h)'}
SHORT=['Australia','China','Japan','Bahrain','Saudi Arabia','Miami','Emilia Romagna','Monaco','Spain','Canada',
       'Austria','Britain','Belgium','Hungary','Netherlands','Italy','Azerbaijan','Singapore','United States','Mexico City',
       'São Paulo','Las Vegas','Qatar','Abu Dhabi']
CODES=['AUS','CHN','JPN','BHR','SAU','MIA','EMR','MON','ESP','CAN','AUT','GBR','BEL','HUN','NED','ITA','AZE','SGP','USA','MEX','SAO','LAS','QAT','ABU']


def analyze(hourly,daily,root):
    root=Path(root);out=root/'data/processed';out.mkdir(parents=True,exist_ok=True)
    desc=daily[DAILY_VARS].describe().T
    pearson=daily[DAILY_VARS].corr(method='pearson')
    spearman=daily[DAILY_VARS].corr(method='spearman')
    hourly_corr=hourly[['temperature_c','relative_humidity_pct','precipitation_mm','wind_speed_kmh']].corr()
    desc.to_csv(out/'descriptive_statistics.csv')
    pearson.to_csv(out/'correlations_race_day_pearson.csv')
    spearman.to_csv(out/'correlations_race_day_spearman.csv')
    hourly_corr.to_csv(out/'correlations_hourly_descriptive_only.csv')
    def extreme(col,mode='max'):
        idx=daily[col].idxmax() if mode=='max' else daily[col].idxmin()
        r=daily.loc[idx]
        return {'race_name':r.race_name,'race_date':r.race_date,'value':float(r[col])}
    summary={'race_days':len(daily),'hourly_rows':len(hourly),
             'warmest_day_mean':extreme('temperature_mean_c'),
             'coolest_day_mean':extreme('temperature_mean_c','min'),
             'wettest_day':extreme('precipitation_total_mm'),
             'windiest_day_mean':extreme('wind_speed_mean_kmh'),
             'most_humid_day_mean':extreme('relative_humidity_mean_pct'),
             'days_with_any_precipitation':int((daily.precipitation_total_mm>0).sum()),
             'days_with_at_least_1mm':int((daily.precipitation_total_mm>=1).sum()),
             'wet_hours_any_positive_mm':int((hourly.precipitation_mm>0).sum()),
             'sum_precipitation_across_24_locations_mm':float(daily.precipitation_total_mm.sum()),
             'race_day_mean_temperature_average_c':float(daily.temperature_mean_c.mean()),
             'race_day_mean_temperature_sample_sd_c':float(daily.temperature_mean_c.std()),
             'overall_hourly_min_temperature_c':float(hourly.temperature_c.min()),
             'overall_hourly_max_temperature_c':float(hourly.temperature_c.max()),
             'pearson_n':len(daily),
             'pearson_correlations':pearson.to_dict(),
             'spearman_correlations':spearman.to_dict()}
    (out/'results_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    return desc,pearson,spearman,summary


def create_figures(hourly,daily,root,show=False):
    """Five distinct views with explicit units and scope captions."""
    root=Path(root);folder=root/'figures';folder.mkdir(parents=True,exist_ok=True)
    sns.set_theme(style='whitegrid',font='DejaVu Sans',font_scale=0.92,
                  rc={'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','axes.titleweight':'bold'})
    paths=[]
    def save(fig,name):
        path=folder/name
        fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white')
        paths.append(path)
        if show: plt.show()
        plt.close(fig)
    x=np.arange(len(daily))
    # Means, ranges and all 24 races in championship order.
    fig,ax=plt.subplots(figsize=(12,4.8))
    colors=plt.cm.coolwarm(plt.Normalize(10,32)(daily.temperature_mean_c))
    ax.vlines(x,daily.temperature_min_c,daily.temperature_max_c,color=colors,lw=3,alpha=.9)
    ax.scatter(x,daily.temperature_mean_c,color=colors,s=46,edgecolor='white',linewidth=.7,zorder=3,label='Local-day mean')
    ax.set(xticks=x,xticklabels=CODES,xlabel='Grand Prix (championship order)',ylabel='Air temperature at 2 m (°C)',
           title='2025 race-day temperatures: mean and hourly range')
    ax.grid(axis='x',visible=False)
    ax.set_title(ax.get_title(),pad=30)
    ax.text(0,1.02,'Dots: mean • Lines: minimum–maximum • ERA5 hourly grid estimates',transform=ax.transAxes,fontsize=9,color='#50555b')
    fig.tight_layout();save(fig,'01_temperature_range.png')
    # A complete rain comparison, including explicitly dry estimates.
    fig,ax=plt.subplots(figsize=(12,4.8))
    bars=ax.bar(x,daily.precipitation_total_mm,color='#247aaf',width=.7)
    ax.bar_label(bars,labels=[f'{v:.1f}' if v>0 else '0' for v in daily.precipitation_total_mm],padding=3,fontsize=8)
    ax.set(xticks=x,xticklabels=CODES,xlabel='Grand Prix (championship order)',ylabel='Precipitation (mm per local race day)',
           title='Race-day precipitation, aligned midnight to midnight')
    ax.set_ylim(0,max(daily.precipitation_total_mm.max()*1.23,1))
    ax.grid(axis='x',visible=False)
    ax.set_title(ax.get_title(),pad=30)
    ax.text(0,1.02,'Next-midnight endpoint closes the final hour; values include liquid-equivalent snow',transform=ax.transAxes,fontsize=9,color='#50555b')
    fig.tight_layout();save(fig,'02_precipitation_totals.png')
    # Distinct paired panels avoid a misleading double axis.
    fig,(ax1,ax2)=plt.subplots(1,2,figsize=(12,6),sharey=True)
    y=np.arange(len(daily))
    ax1.barh(y,daily.relative_humidity_mean_pct,color='#3d9485')
    ax2.barh(y,daily.wind_speed_mean_kmh,color='#7f6ab0')
    ax1.set(yticks=y,yticklabels=SHORT,xlabel='Mean relative humidity (%)',title='Humidity');ax1.invert_yaxis()
    ax2.set(xlabel='Mean wind speed at 10 m (km/h)',title='Wind')
    ax1.set_xlim(0,100)
    fig.suptitle('Full local race-day means across 24 Grands Prix',fontsize=14,fontweight='bold')
    fig.tight_layout();save(fig,'03_humidity_wind.png')
    # Race-day aggregate sample; no p-values or causal wording.
    corr=daily[DAILY_VARS].rename(columns=LABELS).corr()
    fig,ax=plt.subplots(figsize=(7.4,6))
    sns.heatmap(corr,annot=True,fmt='.2f',vmin=-1,vmax=1,center=0,cmap='vlag',square=True,
                linewidths=1,cbar_kws={'label':'Pearson correlation r'},ax=ax)
    ax.set_title('Race-day weather correlations (n = 24)',pad=15)
    ax.set_xticklabels(ax.get_xticklabels(),rotation=35,ha='right')
    ax.set_yticklabels(ax.get_yticklabels(),rotation=0)
    fig.tight_layout();save(fig,'04_race_day_correlations.png')
    # Hour-of-day patterns demonstrate why a full-day mean is not race-time weather.
    heat=hourly.pivot(index='round',columns='hour_local',values='temperature_c')
    fig,ax=plt.subplots(figsize=(12,8))
    sns.heatmap(heat,yticklabels=SHORT,xticklabels=range(24),cmap='YlOrRd',
                cbar_kws={'label':'Air temperature at 2 m (°C)'},ax=ax)
    ax.set(xlabel='Circuit local hour (00:00–23:00)',ylabel='Grand Prix',title='Hourly air temperature on each local race date')
    ax.set_yticklabels(ax.get_yticklabels(),rotation=0)
    fig.tight_layout();save(fig,'05_hourly_temperature_heatmap.png')
    return paths
