# -*- coding: utf-8 -*-
import ScriptEnv
print("ScriptEnv attrs:", [a for a in dir(ScriptEnv) if not a.startswith("__")])
print("Initialize result:", ScriptEnv.Initialize("Ansoft.ElectronicsDesktop"))
print("after init attrs:", [a for a in dir(ScriptEnv) if not a.startswith("__")])
