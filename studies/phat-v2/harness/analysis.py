"""Process-block statistics fixed before PHAT confirmation."""
import math
import statistics as st

# Two-sided 95% Student t critical values for the two- and five-pass protocols.
T95 = {1:12.706204736432095,4:2.7764451051977987}


def log_ratio_summary(ratios):
    logs=[math.log(x) for x in ratios]
    n=len(logs);center=st.mean(logs)
    radius=T95[n-1]*st.stdev(logs)/math.sqrt(n) if n>1 else None
    return dict(ratio=math.exp(center),ci95=None if radius is None else
                [math.exp(center-radius),math.exp(center+radius)],
                pass_range=[min(ratios),max(ratios)],passes=n)


def classify(ratio,margin=1.10):
    return 'win' if ratio>margin else 'loss' if ratio<1/margin else 'near_tie'


def aggregate(comparisons,cases,passes):
    rows=[r for r in comparisons if r['phase']=='combined']
    families=sorted(set(c['family'] for c in cases.values()))
    result=dict(eligible_cases=len(rows),fixed_cases=len(cases),families={},aggregate=None,
                generally_faster=False,claim_scope='fixed synthetic suite, compiled code and uncached mathematics')
    by_family={f:[r for r in rows if r['family']==f] for f in families}
    family_blocks={}
    for f,rr in by_family.items():
        total=sum(c['family']==f for c in cases.values())
        counts={name:sum(classify(r['phat_over_tamerop'])==name for r in rr)
                for name in ('win','near_tie','loss')}
        counts['unresolved']=total-len(rr)
        result['families'][f]=dict(fixed_cases=total,counts=counts)
        if len(rr)==total:
            blocks=[math.exp(st.mean(math.log(r['pass_ratios'][i]) for r in rr)) for i in range(passes)]
            family_blocks[f]=blocks
            result['families'][f]['timing']=log_ratio_summary(blocks)
    if len(rows)!=len(cases):return result  # no survivor-only headline
    blocks=[math.exp(st.mean(math.log(family_blocks[f][i]) for f in families)) for i in range(passes)]
    result['aggregate']=log_ratio_summary(blocks)
    result['equal_case_sensitivity']=log_ratio_summary([
        math.exp(st.mean(math.log(r['pass_ratios'][i]) for r in rows)) for i in range(passes)])
    result['weighted_practical_win_share']=st.mean(result['families'][f]['counts']['win']/result['families'][f]['fixed_cases'] for f in families)
    result['families_favoring_share']=sum(result['families'][f]['timing']['ratio']>1 for f in families)/len(families)
    lower=result['aggregate']['ci95'][0]
    # Require the timing margin also to hold in every paired block and the
    # declared equal-case sensitivity view before using the broad headline.
    result['generally_faster']=(result['weighted_practical_win_share']>=.8 and
        result['families_favoring_share']>=.8 and lower>1.10 and min(blocks)>1.10 and
        result['equal_case_sensitivity']['ci95'][0]>1.10)
    return result
