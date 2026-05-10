
AI Content Studio v2 - Complete RunPod Setup Guide
===================================================
From zero to first video in under 30 minutes.

==============================================================
PART 1 - RUNPOD ACCOUNT SETUP (5 min)
==============================================================

Step 1: Create account
  https://runpod.io -> Sign Up (use Google for speed)

Step 2: Add credit
  Billing -> Add Credit -> $10 minimum
  $10 = ~22 videos at $0.44/hr (RTX 3090, ~26 min/video)
  $25 = ~56 videos (comfortable month of content)

Step 3: Add SSH key (for terminal access)
  Settings -> SSH Public Keys -> Add Key
  
  If you don't have an SSH key, generate one:
  
  On Windows (PowerShell):
    ssh-keygen -t ed25519 -C "your@email.com"
    # Press Enter 3 times for defaults
    # Key saved to: C:\Users\you\.ssh\id_ed25519.pub
    # Copy the .pub content into RunPod SSH key field
  
  On Mac/Linux (Terminal):
    ssh-keygen -t ed25519 -C "your@email.com"
    cat ~/.ssh/id_ed25519.pub
    # Copy output into RunPod SSH key field

==============================================================
PART 2 - NETWORK VOLUME (CRITICAL - saves models between runs)
==============================================================

Without a Network Volume, you re-download 30GB of models
every single pod start. With one, it downloads once.

Step 4: Create Network Volume
  Storage -> Network Volumes -> New Network Volume
  Name:    ai-studio-models
  Size:    60 GB  ($0.07/GB/month = $4.20/month)
  Region:  EU-RO-1 (cheapest) or US-TX-3

  The volume persists between pod starts.
  You only pay the storage fee when pod is stopped.

==============================================================
PART 3 - DEPLOY YOUR FIRST POD (5 min)
==============================================================

Step 5: Deploy a pod
  Pods -> Deploy -> Community Cloud (cheaper) or Secure Cloud

  GPU Selection (in order of preference):
    RTX 3090 24GB   $0.44/hr  BEST VALUE - recommended
    RTX 4090 24GB   $0.74/hr  Fastest
    RTX 3080 10GB   $0.34/hr  Budget (VRAM tight for SDXL)
    A40 48GB        $0.79/hr  Most VRAM - best for batches

  Template: Search "PyTorch" -> select:
    runpod/pytorch:2.2.0-py3.11-cuda12.1.1-devel-ubuntu22.04

  Configuration:
    Container Disk:  30 GB
    Volume Disk:     60 GB  (attach your ai-studio-models volume)
    Volume Path:     /workspace/models
    Expose Ports:    8888 (Jupyter), 22 (SSH)

  Click: Deploy

Step 6: Connect to your pod
  Option A - Jupyter Lab (browser, easiest):
    Pods -> your pod -> Connect -> Jupyter Lab
    Opens a browser IDE - no terminal needed

  Option B - SSH (more control):
    Pods -> your pod -> Connect -> SSH over exposed TCP
    Copy the SSH command shown (like: ssh root@x.x.x.x -p 12345)
    Paste into PowerShell / Terminal on your laptop

==============================================================
PART 4 - FIRST-TIME STUDIO SETUP (15 min, one time only)
==============================================================

Step 7: In the pod terminal, run:

  cd /workspace
  git clone https://github.com/YOUR_USERNAME/ai-studio-v2.git
  cd ai-studio-v2
  
  # OR if you uploaded a zip:
  unzip /workspace/ai-studio-v2.zip -d /workspace/ai-studio-v2
  cd /workspace/ai-studio-v2

Step 8: Run the bootstrap script (installs everything):

  chmod +x scripts/setup_runpod.sh
  bash scripts/setup_runpod.sh

  This takes 15-20 min. It:
    Installs FFmpeg, system packages
    Upgrades pip + setuptools
    Installs all Python packages
    Installs Ollama + pulls Llama 3.1 8B
    Downloads all AI models to /workspace/models (Network Volume)
    Runs a GPU smoke test

  Models downloaded to Network Volume (~30GB total):
    SDXL 1.0 Base    ~6.9GB
    SDXL Refiner     ~6.1GB
    XTTS v2          ~2.5GB
    Whisper large-v3 ~1.5GB
    MusicGen-Medium  ~1.7GB
    Llama 3.1 8B     ~4.7GB
    AnimateDiff      ~1.8GB

Step 9: Configure API keys:

  nano /workspace/ai-studio-v2/.env

  Add your keys:
    YOUTUBE_CLIENT_ID=...
    YOUTUBE_CLIENT_SECRET=...
    RUNPOD_API_KEY=...    (for auto start/stop from laptop)
    SLACK_WEBHOOK_URL=... (optional - review notifications)
    GPU_PRICE_PER_HR=0.44 (for cost tracking)

  Save: Ctrl+O, Enter, Ctrl+X

==============================================================
PART 5 - GENERATING YOUR FIRST VIDEO
==============================================================

Step 10: Start Ollama (in background):

  ollama serve &

Step 11: Run the pipeline:

  cd /workspace/ai-studio-v2

  # Relationship advice video:
  python pipeline.py --theme relationships --topic "How to stop overthinking in relationships"

  # Auto-pick trending topic:
  python pipeline.py --theme motivation --auto

  # Specific format:
  python pipeline.py --theme horror --topic "The thing in my basement" --format full_story

  # Kids bedtime story:
  python pipeline.py --theme kids --topic "The little cloud who couldn't rain" --format bedtime_story

  # Short-form (TikTok/Shorts):
  python pipeline.py --theme finance --topic "Why your savings account is losing you money" --format quick_tip

Step 12: Watch progress
  The pipeline prints each stage with timing.
  Typical breakdown on RTX 3090:
    Trend scan:          30 sec
    Script (Ollama):      3 min
    Voice (XTTS GPU):     3 min
    Music (MusicGen):     4 min
    Images (SDXL x8):     7 min
    Animation (AnimDiff): 8 min
    Subtitles (Whisper):  2 min
    Assembly (FFmpeg):    2 min
    Total:              ~29 min

Step 13: Download your video
  Option A - Jupyter Lab:
    Left panel -> navigate to output/final/
    Right-click video -> Download

  Option B - SCP from laptop (PowerShell):
    scp -P 12345 root@x.x.x.x:/workspace/ai-studio-v2/output/final/*.mp4 C:\Videos\

  Option C - rsync (Mac/Linux):
    rsync -avz -e "ssh -p 12345" root@x.x.x.x:/workspace/ai-studio-v2/output/final/ ./videos/

Step 14: STOP THE POD (important - billing stops)
  RunPod Dashboard -> Pods -> Stop
  OR from terminal:
    runpodctl remove pod POD_ID
  
  Network Volume data persists. Models stay downloaded.
  Next run: start pod, models already there, ready in 2 min.

==============================================================
PART 6 - YOUR 15-MINUTE HUMAN TASK
==============================================================

After pipeline finishes, the terminal shows 3 hook options.

Task 1: Watch the video (2 min)
  Watch at 2x speed. Check for audio sync, weird images.
  If anything is broken: python pipeline.py --session SESSION_ID --skip-to assembly

Task 2: Pick and record your hook (5 min)
  Choose from 3 hook options shown in terminal.
  Record yourself saying it with ENERGY on your phone.
  5 seconds. Natural background is fine.

Task 3: Design thumbnail in Canva (6 min)
  Go to: canva.com -> YouTube Thumbnail (1280x720)
  Use the thumbnail description from your chosen hook.
  Download as PNG.
  
  Pro tips:
  - Big bold text (1-2 words maximum)
  - One dominant emotion on a face
  - High contrast colors for your theme
  - Test at small size (how it looks on mobile)

Task 4: Upload to YouTube
  python src/uploader.py --session SESSION_ID
  It walks you through adding the hook clip + thumbnail.

==============================================================
PART 7 - AUTOMATED DAILY WORKFLOW
==============================================================

Once comfortable, set up cron on the pod for batch generation:

  # Edit cron: crontab -e
  # Generate 1 video every night at 11pm pod time:
  0 23 * * * cd /workspace/ai-studio-v2 && ollama serve & sleep 3 && python pipeline.py --theme relationships --auto >> logs/cron.log 2>&1

  Better: Use the pod_manager.py to control pods from your LAPTOP:

  # On your laptop (after pip install runpod):
  python -c "
  from src.pod_manager import PodManager
  mgr = PodManager()
  print(mgr.get_ssh_command())  # connect after starting
  mgr.start()  # starts pod
  # SSH in and run your pipeline
  # mgr.stop()   # stops pod when done
  "

==============================================================
PART 8 - COST OPTIMIZATION TIPS
==============================================================

1. ALWAYS use Network Volume
   Saves re-downloading 30GB every session = saves 20-30 min GPU time

2. Use Community Cloud when available
   Same hardware, ~30-40% cheaper, occasionally less available

3. Spot pods (even cheaper)
   RunPod -> Spot Instances -> cheaper but can be interrupted
   Good for batch overnight runs

4. Batch your videos
   Running 3 videos in one pod session is cheaper than 3 separate sessions
   Pod startup overhead is ~2-3 min - amortize it over multiple videos

5. Stop immediately when done
   RunPod charges by the second. No idle time.
   Cost of forgetting for 8 hours: ~$3.52

6. Watch the auto-stop:
   Config has auto_stop_after_idle_minutes: 30
   After 30 min of no activity, pod stops itself

Monthly cost example (3 videos/day, RTX 3090):
  GPU time:      ~$12.50 (3 videos x 29 min x 22 days x $0.44/hr)
  Network Volume: $4.20  (60GB x $0.07/GB/month)
  Total:         ~$16.70/month
  Per video:      $0.25

==============================================================
PART 9 - THEME QUICK REFERENCE
==============================================================

python pipeline.py --list-themes

  Theme          Name                    CPM      Best Format
  kids           Kids Educational        $6       bedtime_story
  relationships  Relationships           $12      story_lesson
  motivation     Motivation & Success    $15      story_lesson
  mindfulness    Mindfulness & Sleep     $18      guided_meditation
  horror         Horror Stories          $8       full_story
  finance        Personal Finance        $22      explainer
  fitness        Fitness & Health        $14      education
  history        Historical Stories      $10      narrative

Tip: Finance and Mindfulness have highest CPMs.
     Horror has the highest organic shareability.
     Relationships dominates TikTok watch time.
