"""Synthetic RGB detector tests and a local CPU benchmark; not flight validation."""
from pathlib import Path
import json, math, time, platform
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

H_MIN, H_MAX, S_MIN, V_MIN = 10.0, 45.0, .55, .30

def detect(rgb):
    z = rgb.astype(np.float32) / 255
    r,g,b = z[:,:,0], z[:,:,1], z[:,:,2]
    hi,lo = z.max(axis=2),z.min(axis=2)
    delta = hi-lo
    nz = delta > 1e-6
    h = np.zeros_like(hi)
    rr = nz & (hi == r)
    gg = nz & ~rr & (hi == g)
    bb = nz & ~rr & ~gg
    h[rr] = (60*((g[rr]-b[rr])/delta[rr])) % 360
    h[gg] = 60*((b[gg]-r[gg])/delta[gg]+2)
    h[bb] = 60*((r[bb]-g[bb])/delta[bb]+4)
    sat = np.divide(delta,hi,out=np.zeros_like(hi),where=hi>0)
    mask = (h>=H_MIN)&(h<=H_MAX)&(sat>=S_MIN)&(hi>=V_MIN)
    yy,xx = np.nonzero(mask)
    unseen = set(zip(yy.tolist(),xx.tolist()))
    candidates=[]
    while unseen:
        seed=unseen.pop(); stack=[seed]; pts=[seed]
        while stack:
            y,x=stack.pop()
            for dy in [-1,0,1]:
                for dx in [-1,0,1]:
                    q=(y+dy,x+dx)
                    if q in unseen:
                        unseen.remove(q);stack.append(q);pts.append(q)
        a=np.asarray(pts)
        height=int(np.ptp(a[:,0]))+1; width=int(np.ptp(a[:,1]))+1
        area=len(a); aspect=width/height; fill=area/(width*height)
        if 6<=area<=1000 and .5<=aspect<=2 and fill>=.45:
            candidates.append({'x':float(a[:,1].mean()),'y':float(a[:,0].mean()),
                               'area':area,'width':width,'height':height})
    return candidates

def scene(rng,diameter=4.7462636,blur=0,brightness=1,noise=4,minor_ratio=1,kind='target'):
    size=128
    center=(64+rng.uniform(-.5,.5),64+rng.uniform(-.5,.5))
    yy,xx=np.mgrid[0:size,0:size]
    coverage=np.zeros((size,size),dtype=float)
    if kind!='empty':
        for sy in (np.arange(4)+.5)/4-.5:
            for sx in (np.arange(4)+.5)/4-.5:
                coverage+=(((xx+sx-center[0])/(diameter/2))**2+
                           ((yy+sy-center[1])/(diameter*minor_ratio/2))**2<=1)/16
    bg=np.array([28.,55.,85.]); target=np.array([255.,100.,0.])
    rgb=bg[None,None,:]*(1-coverage[:,:,None])+target[None,None,:]*coverage[:,:,None]
    rgb=np.uint8(np.clip(rgb,0,255))
    if blur: rgb=np.array(Image.fromarray(rgb).filter(ImageFilter.GaussianBlur(blur)))
    rgb=np.uint8(np.clip(rgb.astype(float)*brightness+rng.normal(0,noise,rgb.shape),0,255))
    return rgb,center

def main():
    rng=np.random.default_rng(423)
    groups=[('9 px clear',9,0,1,4,1,'target'),
            ('4.75 px clear',4.7462636,0,1,4,1,'target'),
            ('4.75 px blurred',4.7462636,1.2,1,4,1,'target'),
            ('4.75 px dim',4.7462636,.5,.25,8,1,'target'),
            ('4.75 px oblique',4.7462636,.2,1,4,.4,'target'),
            ('Empty background',4.7462636,0,1,4,1,'empty'),
            ('Same-color circular distractor',4.7462636,0,1,4,1,'distractor')]
    rows=[]; examples=[]
    for name,d,blur,brightness,noise,minor,kind in groups:
        hits=0
        for i in range(100):
            rgb,c=scene(rng,d,blur,brightness,noise,minor,kind)
            candidates=detect(rgb)
            hits+=any(math.hypot(x['x']-c[0],x['y']-c[1])<=2 for x in candidates) if kind=='target' else bool(candidates)
            if i==0: examples.append((name,rgb,candidates))
        rows.append({'condition':name,'frames':100,'positive_frames':hits,'rate_percent':hits,
                     'rate_type':'recall' if kind=='target' else 'false_positive_frame_rate'})
    # Benchmark one full-resolution RGB frame with a sparse target on THIS host CPU.
    frame=np.empty((1080,1920,3),dtype=np.uint8);frame[:]=[28,55,85]
    tiny,_=scene(rng)
    frame[476:604,896:1024]=tiny
    for _ in range(3): detect(frame)
    times=[]
    for _ in range(30):
        start=time.perf_counter(); detect(frame);times.append((time.perf_counter()-start)*1000)
    fx=1920/(2*math.tan(math.radians(2.4)/2))
    result={'seed':423,'test_scope':'Synthetic 128x128 RGB images; not field performance',
            'thresholds':{'hue_deg':[10,45],'saturation_min':.55,'value_min':.30,
                          'area_px':[6,1000],'aspect':[.5,2],'fill_min':.45},
            'tests':rows,'geometry':{'fx_px':fx,'target_px_at_2414m':fx*.25/2414,
                                    'continuous_disk_area_px':math.pi*(fx*.25/2414/2)**2,
                                    'projected_area_ratio_limit':6/(math.pi*(fx*.25/2414/2)**2)},
            'cpu_benchmark':{'host_arch':platform.machine(),'python':platform.python_version(),
                'numpy':np.__version__,'frame':'1920x1080 RGB, sparse candidate mask',
                'warmup':3,'samples':30,'p50_ms':float(np.percentile(times,50)),
                'p95_ms':float(np.percentile(times,95)),'max_ms':max(times)},
            'warning':'CPU measurements do not establish Jetson or GPU performance.'}
    out=Path(__file__).parent
    (out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    canvas=Image.new('RGB',(800,450),'white');draw=ImageDraw.Draw(canvas)
    for i,(name,rgb,cs) in enumerate(examples):
        x=(i%4)*200;y=(i//4)*215
        crop=Image.fromarray(rgb).crop((48,48,80,80)).resize((160,160),Image.Resampling.NEAREST)
        canvas.paste(crop,(x+10,y+30));draw.text((x+5,y+5),name,fill='black')
        draw.text((x+5,y+195),f'Candidates: {len(cs)}',fill='black')
    canvas.save(out/'synthetic-examples.png')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
