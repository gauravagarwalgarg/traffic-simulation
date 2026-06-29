import sys

if "--web" in sys.argv or "-w" in sys.argv:
    from engine.webapp import start_web
    start_web()
elif "--viz" in sys.argv or "-v" in sys.argv:
    from engine.visualizer import run_visual
    run_visual()
else:
    from engine.runner import main
    main()
