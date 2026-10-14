PROGRAM PLC_PRG
VAR
    xStart : BOOL;
    xPermit : BOOL;
    xSensor : BOOL;
    xFault : BOOL;
    xReset : BOOL;
    eState : USINT;
    xValve : BOOL;
    xAlarm : BOOL;
    tonTimeout : TON;
    nOverwrite : INT;
    nScan : UDINT;
    aValues : ARRAY[0..2] OF INT := [17, 23, 31];
    stFeedback : ST_DebugFeedback;
END_VAR
