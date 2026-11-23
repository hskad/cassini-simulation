# Cost-Aware Communication Scheduling for Distributed Deep Learning
## Simple & Plain English Defense Script (12–15 Minutes)
**Speaker**: Daksh Agarwal (Roll No: 230101123)  
**Project**: BTP-1 Capstone Project Presentation  
**Department**: Computer Science & Engineering, IIT Guwahati  

---

### How to Use This Script
> 💡 **Keep it simple and natural**:  
> * **Look at the slide** to see your visual cue (the bullet point, diagram, or table).  
> * Press **`[CLICK]`** to reveal the next animation on screen.  
> * Speak the explanation in **plain, simple words**. You don't have to sound like a textbook—just explain the logic clearly as if explaining it to a fellow engineer.

---

### Timing & Click Map (12 to 14 Minutes)

| Slide | What You're Talking About | Clicks | Target Time | Clock |
| :---: | :--- | :---: | :---: | :---: |
| **0** | Introduction & The Big Question | 0 | 0:30 min | `00:00 – 00:30` |
| **1** | Why Network Traffic Jams Happen & Two Overlooked Costs | **3** | 0:45 min | `00:30 – 01:15` |
| **2** | Two Questions & Our Contributions | **4** | 0:40 min | `01:15 – 01:55` |
| **3** | The Core Idea: Taking Turns on the Network | 0 | 0:50 min | `01:55 – 02:45` |
| **4** | How to Schedule Multiple Links (Trees vs Cycles) | **3** | 0:45 min | `02:45 – 03:30` |
| **5** | Scoring the Network Traffic (1.0 = Zero Traffic Jams) | **2** | 0:45 min | `03:30 – 04:15` |
| **6** | The Hidden Penalty: Pausing Wastes GPU Time | **2** | 0:45 min | `04:15 – 05:00` |
| **7** | Five Scheduling Strategies We Tested | 0 | 0:40 min | `05:00 – 05:40` |
| **8** | The Solution: The Benefit Rule in Plain Words | **2** | 0:50 min | `05:40 – 06:30` |
| **9** | A Simple Example: Why Pausing Hurts Short Jobs | **3** | 1:00 min | `06:30 – 07:30` |
| **10** | How the Scheduler Decides (The Flowchart) | **3** | 0:40 min | `07:30 – 08:10` |
| **11** | The Workloads We Tested (Up to 10,000 Jobs) | **3** | 0:45 min | `08:10 – 08:55` |
| **12** | **The Big Result**: Doing Nothing Beats Vanilla Cassini! | **2** | 1:05 min | `08:55 – 10:00` |
| **13** | Why It Works: Cutting 73% of Wasted Waiting Time | **2** | 0:50 min | `10:00 – 10:50` |
| **14** | What if We Guess Remaining Work Wrong? (Robustness) | **3** | 0:45 min | `10:50 – 11:35` |
| **15** | The LCM Math Problem: Why Full Cycles Take 33 Hours | **1** | 0:50 min | `11:35 – 12:25` |
| **16** | Is a 600 ms Window Good Enough? (Yes, 99.9% Accurate) | **3** | 0:45 min | `12:25 – 13:10` |
| **17** | Summary: Three Practical Lessons | **4** | 0:45 min | `13:10 – 13:55` |
| **18** | Future Work for BTP-2: Handling Real-World Jitter | **4** | 0:40 min | `13:55 – 14:35` |
| **19** | Thank You & Questions | 0 | 0:25 min | `14:35 – 15:00` |

---

## Slide 0: Title Slide
* **Visual on screen**: Title, your name (*Daksh Agarwal*), Roll No (*230101123*).
* **Clicks**: None (`00:00 – 00:30`)

> "Good morning, respected professors. My name is **Daksh Agarwal**, Roll Number **230101123**, and today I am presenting my BTP-1 project:  
> **Cost-Aware Communication Scheduling for Distributed Deep Learning**.  
>
> The subtitle asks a very simple question:  
> ***When is a phase shift worth its pause?***  
> In other words, if we pause a training job to avoid a network traffic jam, when does that pause actually help us, and when does it make things worse? Let's take a look."

---

## Slide 1: Communication is the bottleneck, and two problems are overlooked
* **Clicks**: 3 clicks (`00:30 – 01:15`)

*(On slide load — glance at bullet 1)*
> "Today, GPUs calculate extremely fast, but the network cables connecting them cannot keep up. When multiple AI training jobs run together in a cluster, they all try to send their data at the exact same moment. This creates severe network traffic jams."

**`[CLICK]`** *(Glance at bullet 2)*
> "Standard network tools only react after the network is already jammed. So recent research, like Cassini, proposed a smart idea: let's **time-shift** jobs—meaning, let's delay one job slightly so they take turns and communicate peacefully."

**`[CLICK]`** *(Glance at red box: "1. Shifts are not free")*
> "However, existing papers overlooked two big practical problems.  
> First, **pausing is not free**. To shift a job, you have to force expensive GPUs to sit completely idle. If a job is short, that waiting time can easily waste more time than the network collision itself!"

**`[CLICK]`** *(Glance at blue box: "2. LCM explosion")*
> "Second, **the LCM explosion**. If jobs have different training cycle lengths, finding when they overlap requires calculating their Least Common Multiple. In practice, that math explodes into gigabytes of data and hours of calculation."

---

## Slide 2: Research questions and contributions
* **Clicks**: 4 clicks (`01:15 – 01:55`)

*(On slide load — glance at Question 1)*
> "This leads to two simple questions:  
> First: *When does avoiding network traffic justify the time lost to pausing?*"

**`[CLICK]`** *(Glance at Question 2)*
> "And second: *If we only look at a small 600-millisecond time window instead of doing hours of math, do we lose scheduling quality?*"

**`[CLICK]`** *(Glance at Contribution 1: Benefit Rule)*
> "Here are our answers:  
> First, we designed the **Benefit Rule**—a simple check that only pauses a job if it's truly profitable. This speeds up short jobs by **9.3%**."

**`[CLICK]`** *(Glance at Contribution 2: Robustness)*
> "Second, we showed this rule is very safe: even if our estimates of remaining work are wrong by 50%, it still works reliably."

**`[CLICK]`** *(Glance at Contribution 3: LCM study)*
> "And third, we proved that looking at just a 600-millisecond window is fast, practical, and achieves 99.9% of the optimal schedule."

---

## Slide 3: Time shifting: a simple example
* **Clicks**: None (`01:55 – 02:45`)

*(Look directly at the top and bottom timelines)*
> "Here is a simple picture of how time shifting works.  
> Suppose two identical jobs share one network cable. Each job computes for 60 milliseconds and then communicates for 40 milliseconds.  
>
> In **Case (a)** at the top, without coordination, both jobs finish computing at the exact same second and try to send data together. The red boxes show the collision—packets get stuck in switch queues, and both jobs slow down.  
>
> In **Case (b)** at the bottom, we intentionally pause Job B by 40 milliseconds at the very beginning. Look at what happens after that: when Job A is sending data, Job B is computing. And when Job B is sending data, Job A is computing.  
> They take turns perfectly with zero collisions!  
> But notice the catch: Job B had to sit completely idle for 40 milliseconds at the start to get this alignment."

---

## Slide 4: Compatibility and affinity graphs
* **Clicks**: 3 clicks (`02:45 – 03:30`)

*(On slide load — glance at bullet 1)*
> "To measure how well jobs fit together, schedulers calculate a **Compatibility Score**. A score of 1.0 means zero collisions, while lower scores mean bad traffic jams."

**`[CLICK]`** *(Glance at bullet 2)*
> "Across a whole cluster, we draw an **Affinity Graph**, where circle nodes are training jobs, orange squares are shared network links, and the numbers are the required start delays."

**`[CLICK]`** *(Glance at diagram (a) - Tree)*
> "If the graph looks like a **Tree**—as in diagram (a)—it's easy. We start from a root job and assign clean start delays to everyone: 40 milliseconds for Job 2 and 25 milliseconds for Job 3."

**`[CLICK]`** *(Glance at diagram (b) - Cycle)*
> "However, if the links form a **Cycle**—as in diagram (b)—Link A demands a 40-millisecond delay, but Link B demands a 55-millisecond delay for the same job. Since one job cannot have two different start times, this is a conflict, and the scheduler must reject this placement."

---

## Slide 5: System model: link traffic and compatibility score
* **Clicks**: 2 clicks (`03:30 – 04:15`)

*(On slide load — glance at the top equation)*
> "Slide 5 shows the basic math.  
> Because machine learning runs in loops, each job creates a repeating wave of traffic. When we shift a job by an offset $\theta_j$, we just slide that wave sideways. The total traffic on any link is simply the sum of what all running jobs are sending."

**`[CLICK]`** *(Glance at the score equation)*
> "The **Compatibility Score** $S_\ell$ checks whether that total traffic exceeds the link's physical bandwidth limit $C_\ell$. Any traffic that overflows the limit gets penalized."

**`[CLICK]`** *(Glance at the physical meaning box)*
> "In plain terms: a score of 1.0 means the network never overflows and packets flow without queuing. Lower scores mean severe congestion."

---

## Slide 6: System model: shift delay, contention and completion time
* **Clicks**: 2 clicks (`04:15 – 05:00`)

*(On slide load — glance at the first formula)*
> "Now, here is the cost that previous schedulers ignored: **Forward Shift Delay**.  
> You cannot travel backwards in time. If you want to move a job to a new time slot, you must make the GPUs pause and wait for that slot to arrive. During that time, zero training progress happens."

**`[CLICK]`** *(Glance at completion time formula)*
> "Looking at the completion time formula: a job's total time depends on three things: the time already spent, any time spent paused waiting for shifts, and the remaining training work stretched out by network slowdown."

**`[CLICK]`** *(Glance at the core trade-off box)*
> "This is the core trade-off: **you are paying a guaranteed pause delay right now, hoping to save network time in the future**. If a job is almost finished, paying that pause is guaranteed to make it slower!"

---

## Slide 7: Five policies, same candidate offsets
* **Clicks**: None (`05:00 – 05:40`)

*(Glance down the table rows)*
> "To test this trade-off, we compared five different policies on the exact same proposed shifts:  
> * **Uncoordinated**: Standard FIFO. It never pauses any job.  
> * **Vanilla Cassini**: The state-of-the-art scheduler from NSDI. It always pauses a job if it helps network score, completely ignoring the pause cost.  
> * **Score Control**: Only shifts if the score strictly improves, but still ignores the pause penalty.  
> * **Cooldown**: Waits 100 milliseconds between shifts.  
> * And our **Benefit Rule**: Compares the expected network savings against the pause delay before making a decision."

---

## Slide 8: The Benefit Rule: evaluating shift profitability
* **Clicks**: 2 clicks (`05:40 – 06:30`)

*(On slide load — glance at formula $\widehat{L}_0$)*
> "The Benefit Rule does something very straightforward.  
> First, it estimates completion time under the **current plan**, $\widehat{L}_0$: what happens if we don't pause, and just let the job run through current network traffic?"

**`[CLICK]`** *(Glance at formula $\widehat{L}_1$)*
> "Second, it estimates completion time under the **proposed shift**, $\widehat{L}_1$: the job gets cleaner network traffic, but has to pay the upfront pause delay $d_j$."

**`[CLICK]`** *(Glance at decision rule block)*
> "The rule is simple: **only accept the shift if the network time saved is strictly bigger than the pause delay**.  
> If the pause delay is bigger than the saving, we reject it and let the job keep running immediately. It takes less than a microsecond to check."

---

## Slide 9: A Simple Example: Why Pausing Hurts Short Jobs
* **Clicks**: 3 clicks (`06:30 – 07:30`)

*(On slide load — glance at scenario bullet)*
> "Slide 9 shows this clearly with real numbers.  
> Suppose shifting a job cleans up the network and saves 0.3 milliseconds for every millisecond of work left."

**`[CLICK]`** *(Glance at upfront cost bullet)*
> "To get this alignment, the job has to pause for 40 milliseconds."

**`[CLICK]`** *(Glance at the table)*
> "Now look at the two cases in the table:  
> * **Case 1: A Short Job** (with 100 ms of work left).  
> The network saving is $0.3 \times 100 = 30$ milliseconds. But the pause cost is 40 milliseconds! The job ends up **10 milliseconds slower**. Pausing it was a bad idea. Vanilla Cassini pauses it anyway. The Benefit Rule **rejects** it!  
> * **Case 2: A Long Job** (with 1000 ms of work left).  
> Saving 30% gives 300 milliseconds. Paying a 40-millisecond pause yields a **net profit of 260 milliseconds**. The Benefit Rule happily **accepts** it!"

**`[CLICK]`** *(Glance at core economic insight box)*
> "The takeaway is intuitive: **long jobs run long enough to make a pause worthwhile. Short jobs do not.** Unconditional shifting blindly harms short jobs."

---

## Slide 10: How the Scheduler Decides (The Flowchart)
* **Clicks**: 3 clicks (`07:30 – 08:10`)

*(On slide load — glance at the flowchart)*
> "Slide 10 shows the decision flow inside the scheduler. When a shift is proposed, the scheduler calculates the expected finish time with and without the shift."

**`[CLICK]`** *(Glance at green outcome)*
> "If the time saved is positive, it goes down the green path: the shift is approved, and the job takes its pause."

**`[CLICK]`** *(Glance at red outcome)*
> "If the pause delay is bigger than the savings, it goes down the red path: the shift is dropped, and the job continues running without any delay."

**`[CLICK]`** *(Glance at the bottom alert box)*
> "In our experiments, setting $\varepsilon = 0$ means any shift that saves net time gets approved."

---

## Slide 11: The Workloads We Tested (Up to 10,000 Jobs)
* **Clicks**: 3 clicks (`08:10 – 08:55`)

*(On slide load — glance at the table)*
> "We tested this inside an event-driven packet simulator across five workloads—from 50 jobs up to 10,000 jobs across 32 network links, with 50 Gbps bandwidth."

**`[CLICK]`** *(Glance at workload profiles)*
> "Crucially, our Short workload models jobs that run only 1 to 5 iterations. This matches real datacenter tasks like hyperparameter search and trial runs."

**`[CLICK]`** *(Glance at primary metric)*
> "Our main metric is the percentage speedup in Job Completion Time compared to Vanilla Cassini."

**`[CLICK]`** *(Glance at robustness tests)*
> "We also tested whether the scheduler works if our runtime estimates have up to 50% error."

---

## Slide 12: The Big Result: Doing Nothing Beats Vanilla Cassini!
* **Clicks**: 2 clicks (`08:55 – 10:00`)

*(Look directly at row 3: Short workload)*
> "Here is the most important result of our work. The table shows completion time speedup over Vanilla Cassini—positive numbers mean faster runs.  
>
> Look at the third row, the **Short workload**:  
> **Uncoordinated FIFO execution is +2.28% faster than Vanilla Cassini!**  
> That means doing absolutely nothing beats a sophisticated phase-shifting scheduler! Why? Because Vanilla Cassini was pausing jobs all over the place, wasting more time in idle pauses than it ever saved on the network."

**`[CLICK]`** *(Glance at left box: Short jobs)*
> "Our **Benefit Rule fixes this completely**, delivering a **9.30% speedup** on short jobs—reaching up to 10.8% on individual seeds, and cutting tail latency by 8%."

**`[CLICK]`** *(Glance at right box: Large clusters)*
> "Now look at the bottom rows: on **Large clusters with long jobs**, doing nothing fails badly—it's 32% to 45% slower because long jobs collide continuously.  
> Here, the Benefit Rule matches the best policy at **+3.11% speedup**, because long jobs easily recover the pause cost.  
> Our rule wins in both scenarios."

---

## Slide 13: Why It Works: Cutting 73% of Wasted Waiting Time
* **Clicks**: 2 clicks (`10:00 – 10:50`)

*(Look at the bar chart)*
> "Slide 13 shows exactly why our rule wins.  
> Look at the bar chart: under Vanilla Cassini, jobs spent an average of **110 milliseconds** sitting paused doing zero work.  
> Under our Benefit Rule, shown by the green bar, that idle pause drops to just **29 milliseconds**—a **73% cut in wasted delay**! The rule threw away 70% of bad shifts, only keeping the 144 shifts that actually helped."

**`[CLICK]`** *(Glance at parameter sensitivity)*
> "Even if we require a 5-millisecond minimum profit margin, it still gives up to 9.9% gains, showing it doesn't need delicate tuning."

**`[CLICK]`** *(Glance at bottom alert box)*
> "And the bottom box explains why simple timers fail: a timer just counts clock seconds, not remaining work. It blocks good shifts for new long jobs, and allows wasteful shifts for jobs that are about to finish."

---

## Slide 14: What if We Guess Remaining Work Wrong?
* **Clicks**: 3 clicks (`10:50 – 11:35`)

*(Look at the line plot)*
> "What if the scheduler cannot predict exactly how many iterations a job has left?  
> On Slide 14, we tested errors from $-50\%$ underestimation to $+50\%$ overestimation."

**`[CLICK]`** *(Glance at bullet 1)*
> "Across all 60 tests, the Benefit Rule consistently beats Vanilla Cassini, no matter the error."

**`[CLICK]`** *(Glance at bullets 2 and 3)*
> "On short jobs, speedups stay high—between 8% and 10.3%. On large clusters, gains stay steady at 1%."

**`[CLICK]`** *(Glance at intuition box)*
> "The reason is simple: if you underestimate work, the scheduler acts cautiously like FIFO. If you overestimate, it acts like Vanilla. In neither case does it fail."

---

## Slide 15: The LCM Math Problem: Why Full Cycles Take 33 Hours
* **Clicks**: 1 click (`11:35 – 12:25`)

*(Look at the timeline showing Job A and Job B)*
> "Now let's look at our second challenge: **The LCM Explosion**.  
> In the picture, Job A repeats every 100 milliseconds and Job B repeats every 140 milliseconds. Their combined pattern takes 700 milliseconds to repeat.  
> If a scheduler only looks at a 600-millisecond window—shown by the red dashed line—it misses the collision at 660 milliseconds."

**`[CLICK]`** *(Glance at bottom explosion box)*
> "So why not just calculate the full repeat pattern? Look at the box:  
> If you have just four realistic jobs with prime periods—101, 103, 107, and 109 milliseconds—their true repeat cycle takes **over 33 hours**, and requires **almost 2 Gigabytes of memory** just to evaluate one candidate shift!  
> An online scheduler cannot wait 33 hours to place a job. In contrast, a 600-millisecond window takes **less than one millisecond**."

---

## Slide 16: Is a 600 ms Window Good Enough?
* **Clicks**: 3 clicks (`12:25 – 13:10`)

*(Look at the lines on the plot)*
> "Slide 16 answers whether truncating to 600 milliseconds hurts schedule quality across seven different period families."

**`[CLICK]`** *(Glance at bullet 1)*
> "When the true LCM is under 600 milliseconds, the score is exact. When the LCM is longer, the score is slightly optimistic by 6% to 8%."

**`[CLICK]`** *(Glance at bullets 2 and 3)*
> "Expanding the window to 1200 ms reduces that error. But crucially, candidate shift *rankings* do not change."

**`[CLICK]`** *(Glance at near-optimal alert box)*
> "As shown in the alert box: a 600-millisecond window makes decisions within **0.08 percentage points** of an exhaustive 33-hour search! The scores are slightly optimistic, but the scheduling decisions are near-optimal."

---

## Slide 17: Summary: Three Practical Lessons
* **Clicks**: 4 clicks (`13:10 – 13:55`)

*(On slide load — glance at bullet 1)*
> "To summarize our findings from BTP-1, here are three practical rules:  
> 1. **Pausing has an upfront cost.** On short jobs, doing nothing beats unconditional shifting by 2.3%."

**`[CLICK]`** *(Glance at bullet 2)*
> "2. **Filter shifts by net benefit.** The Benefit Rule cuts wasted pause delay by 73% and speeds up short jobs by 9.3%."

**`[CLICK]`** *(Glance at bullet 3)*
> "3. **Keep scoring windows short.** A 600-millisecond window captures 99.9% of schedule quality in under one millisecond."

**`[CLICK]`** *(Glance at bullet 4)*
> "4. **Don't use static timers**, because they don't track remaining work."

**`[CLICK]`** *(Glance at practical deployment box)*
> "Our rule requires only iteration counts and link scores, meaning it can be plugged directly into Slurm or Kubernetes clusters today."

---

## Slide 18: Future Work for BTP-2: Handling Real-World Jitter
* **Clicks**: 4 clicks (`13:55 – 14:35`)

*(On slide load — glance at bullet 1)*
> "Looking ahead to BTP-2: in real GPU hardware, iterations naturally vary by 2% to 5% due to data loading and thermal throttling. Over hundreds of iterations, perfectly spaced jobs drift and start colliding again."

**`[CLICK]`** *(Glance at bullet 2)*
> "Current schedulers only set offsets once at launch and assume jobs stay synchronized forever."

**`[CLICK]`** *(Glance at Item 1: Resynchronisation checkpoints)*
> "For BTP-2, we plan two mechanisms:  
> First, **Resynchronisation checkpoints**: periodically nudging drifting jobs back into their assigned time slots."

**`[CLICK]`** *(Glance at Item 2: Elastic communication cushions)*
> "Second, **Elastic communication cushions**: small timing buffers that absorb timing jitter without pausing GPUs."

**`[CLICK]`** *(Glance at final bullet)*
> "We plan to test both mechanisms in cluster simulations and on physical multi-GPU servers."

---

## Slide 19: Thank You & Questions
* **Visual Anchor**: *Thank you! Questions & Discussion*
* **Clicks**: None (`14:35 – 15:00`)

> "Thank you very much for your time and attention.  
> I am happy to answer any questions, or demonstrate our simulation code live. Thank you!"

---

### Three Simple 1-Sentence Answers for Evaluator Questions

1. **"Why did Cassini claim big gains if shifting hurts short jobs?"**  
   *Answer*: *"Cassini only tested large training jobs with thousands of iterations, where pausing once is easily recovered. We tested what happens in modern short fine-tuning tasks where jobs only run 5 to 25 iterations."*

2. **"Does computing your Benefit Rule slow down scheduling?"**  
   *Answer*: *"No, it takes less than one microsecond—just three basic arithmetic operations comparing expected savings to the pause."*

3. **"Why not use a 1200 ms window instead of 600 ms?"**  
   *Answer*: *"Because 600 ms is already 99.9% optimal. Doubling the window doubles computation time for less than 0.05% gain."*
