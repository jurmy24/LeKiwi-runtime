# LeKiwi-runtime

Controlling LeKiwi (the robot) can be done either on the Pi host (`LeKiwi`) or from the computer client via `LeKiwiClient`.

## How to run the robot

... on a preconfigured pi (i.e. lerobot installed, conda env setup, etc...)

> Setup on Pi host

```bash
ssh lekiwi@lekiwi.local
```

One you've `ssh`'d in run the following:

```bash
cd Documents/lerobot
conda activate lerobot
```

> Setup on local computer client

```bash
cd lerobot
conda activate lerobot
```

### Run teleoperation

> First call this from the Pi host

```bash
# Without cameras
python -m lerobot.robots.lekiwi.lekiwi_host --robot.id=biden_kiwi --robot.cameras="{}"

# With cameras
python -m lerobot.robots.lekiwi.lekiwi_host \
    --robot.id=biden_kiwi \
    --robot.cameras="{front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, "wrist": {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}}" \
```

> And this from the computer client

```bash
python examples/lekiwi/teleoperate.py
```

My port
"/dev/tty.usbmodem5AB90687441"
