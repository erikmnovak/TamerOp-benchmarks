if LoadPackage("qpa")<>true then Print("ERROR: QPA unavailable\n");QUIT_GAP(1);fi;
info:=NanosecondsSinceEpochInfo();;
if not info.Monotonic or not info.Reliable or info.Resolution<=0 then
 Print("ERROR: Timing requires a verified monotonic GAP clock\n");QUIT_GAP(1);
fi;
Print("VERSION|",GAPInfo.Version,"|",PackageInfo("qpa")[1].Version,"\n");
Print("CLOCK|",info.Method,"|",info.Monotonic,"|",info.Reliable,"|",info.Resolution,"\n");
lasttime:=NanosecondsSinceEpoch();;negative:=0;;equal:=0;;mindelta:=10^20;;maxdelta:=0;;
for i in [1..100000] do
 now:=NanosecondsSinceEpoch();delta:=now-lasttime;
 if delta<0 then negative:=negative+1;fi;
 if delta=0 then equal:=equal+1;fi;
 if delta>0 and delta<mindelta then mindelta:=delta;fi;
 if delta>maxdelta then maxdelta:=delta;fi;
 lasttime:=now;
od;
if negative<>0 then Print("ERROR: Clock moved backwards\n");QUIT_GAP(1);fi;
Print("INCREMENTS|",negative,"|",equal,"|",mindelta,"|",maxdelta,"\n");
for duration in [20000,50000,100000] do
 t:=NanosecondsSinceEpoch();MicroSleep(duration);delta:=NanosecondsSinceEpoch()-t;
 if delta<900*duration then Print("ERROR: Clock interval too short\n");QUIT_GAP(1);fi;
 Print("SLEEP|",duration,"|",delta,"\n");
od;
for b in [1..5] do
 t:=NanosecondsSinceEpoch();for i in [1..100000] do now:=NanosecondsSinceEpoch();od;
 Print("CALL_LOOP|",b,"|",NanosecondsSinceEpoch()-t,"\n");
od;
t:=NanosecondsSinceEpoch();total:=0;;for i in [1..1000000] do total:=total+i;od;
if total<>500000500000 then Print("ERROR: Arithmetic checksum failed\n");QUIT_GAP(1);fi;
Print("BUSY|",NanosecondsSinceEpoch()-t,"|",total,"\n");
Print("COMPLETE\n");QUIT_GAP(0);
