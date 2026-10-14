(* Hardware-independent scenario model. TON uses simulation wall-clock time. *)
nScan := nScan + 1;
nOverwrite := 0;
stFeedback.xReady := TRUE;
stFeedback.nValue := 7;
tonTimeout(IN := eState = 10, PT := T#5s);
IF xFault THEN
    eState := 90;
END_IF;
CASE eState OF
    0:
        IF xStart AND xPermit THEN
            eState := 10;
        END_IF;
    10:
        IF NOT xPermit THEN
            eState := 90;
        ELSIF xSensor THEN
            eState := 20;
        ELSIF tonTimeout.Q THEN
            eState := 90;
        END_IF;
    20:
        eState := 30;
    30:
        IF xReset THEN eState := 0; END_IF;
    90:
        IF xReset AND NOT xFault THEN eState := 0; END_IF;
END_CASE;
xValve := (eState = 10) AND xPermit AND NOT xFault;
xAlarm := eState = 90;
