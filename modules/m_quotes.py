"""
random quote on connect
"""

import random

from handle.core import IRCD, Hook

quotes = """Men are from Mars. Women are from Venus. Computers are from hell.
Computer /nm./: a device designed to speed and automate errors.
Hardware /nm./: the part of the computer that you can kick.
Maniac /n./ An early computer built by nuts.
RAM /abr./: Rarely Adequate Memory.
Programmer /n./ A red-eyed, mumbling mammal capable of conversing with inanimate objects.
Multitasking /adj./ 3 PCs and a chair with wheels.
Plonk /excl./: The sound a newbie makes as he falls to the bottom of a kill file.
hURL /n./: a link to a web site that makes you want to puke.
SUPERCOMPUTER: what it sounded like before you bought it.
If it's really a supercomputer, how come the bullets don't bounce off when I shoot it? - The Covert Comic.
A computer is like an Old Testament god, with a lot of rules and no mercy. - Joseph Campbell
I dropped my computer on my foot! That Megahurtz!
A computer's attention span is as long as its power cord.
586: The average IQ needed to understand a PC.
Memory is like an orgasm. It's a lot better if you don't have to fake it.
If it jams, force it. If it breaks, it needed replacing anyway.
A bus station is where a bus stops. A train station is where a train stops. On my desk I have a workstation...
Want to come see my HARD DRIVE? I promise it isn't 3.5 inches and it ain't floppy. - Geek pick-up line.
If you torture the data enough, it will confess. - Ronald Coase
If you give someone a program, you will frustrate them for a day; if you teach them how to program, you will frustrate them for a lifetime.
ASCII stupid question, get a stupid ANSI!
Use the source, Luke...
Programming is an art form that fights back.
MacOS, Windows, BeOS: they're all just Xerox copies.
Whenever you think you have a clever programming trick... forget it!
Managing senior programmers is like herding cats. - Dave Platt
Your program is sick! Shoot it and put it out of its memory.
/* You are not expected to understand this */
To define recursion, we must first define recursion.
ERROR: Computer possessed; Load EXOR.SYS? [Y/N]
Linux is only free if your time is worthless.
Linux: find out what you've been missing while you've been rebooting Windows NT.
unzip; strip; touch; finger; mount; fsck; more; yes; unmount; sleep.
Profanity is the one language all programmers know best.
It's 5.50 a.m... Do you know where your stack pointer is?
#define QUESTION ((bb) || !(bb)) - Shakespeare
The more I C, the less I see.
Confucius say: He who play in root, eventually kill tree.
Unix is the answer, but only if you phrase the question very carefully.
C++: Hard to learn and built to stay that way.
Java is, in many ways, C++--  - Michael Feldman.
They don't make bugs like Bunny anymore. - Olav Mjelde
If debugging is the process of removing software bugs, then programming must be the process of putting them in
When the only tool you own is a hammer, every problem you encounter resembles a nail
System Error: press F13 to continue...
To err is human, but for a real disaster you need a computer
Computers make very fast, very accurate mistakes
Life would be so much easier if we only had the source code
Who is this 'General Failure' and why is he reading my disk?
hAS aNYONE sEEN MY cAPSLOCK kEY?
I'm in the computer business, I make Out-Of-Order signs
Kevorkian Virus: helps your computer shut down whenever it wants to.
          [OUT OF QUOTES, PLEASE ORDER MORE]
Insert Something Funkeh... err... There! -->
Cannot delete tmp150---3.tmp: There is not enough free disk space. Delete one or more files to free disk space, and then try again.
File not found. Should I fake it? (Y/N)
The definition of an upgrade: Take old bugs out, put new ones in
If it's not on fire, it's a software problem
It's a little-known fact that the Y1K problem caused the Dark Ages.
Artificial Intelligence usually beats natural stupidity.
Making fun of AOL users is like making fun of the kid in the wheel chair.
Daddy, why doesn't this magnet pick up this floppy disk?
Daddy, what does FORMATTING DRIVE C mean?
See, Daddy? All the keys are in alphabetical order now.
Enter any 11-digit prime number to continue...
ASCII and ye shall receive.
The web is a dominatrix. Every where I turn, I see little buttons ordering me to Submit.
<FrostyCoolSlug> NO, You cannot dial 999, I'm downloading my mail ;/
640K ought to be enough for anybody. - Bill Gates, 1981
Windows not found, [P]arty, [C]elebrate, [D]rink?
English, the Microsoft of languages...
It's been said that Bill Gates named his company after his dick...
Ever notice how fast Windows runs? Neither did I
If at first you don't succeed, work for Microsoft
We are Microsoft. Resistance Is Futile. You Will Be Assimilated
"Microsoft Works." - Oxymoron
Windows isn't a virus, viruses do something
PANIC! buffer = :NickServ WRITE_DB(3). <-- JUST KIDDING!
It just keeps going and going and going and going and goi <BANG>
All that I know is that nukes are comming from 127.0.0.1
I know all about the irc and the mirc cops.
M re ink n ed d, ple s  r fil
Please refrain from feeding the IRC Operators. Thank you.
I know all about mirc stuff, hmm... I think this channel is experiencing packet loss...
MacDonalds claims Macintosh stole their next idea of the iMac.
I can't hold her any longer, captain, she's gonna bl... sorry, got caught up in the moment
I recommend purchasing a Cyrix CPU for testing nuclear meltdowns
Is it an international rule to have the worst picture possible on your driver license?
Have you hugged your services coder, today?
Ever wonder why they make the colon flash on alarm clocks?
What's this? Blue screen with a VXD error?! I'VE BEEN NUKED!
Do-do-bop-doo-doo-do-do-doo... For those of you who know that song, you have problems...
Be wery wery quiet... hunting wabbit...
I've been IRC Nuked"Great warrior?  War does not make one great." - Yoda
"I find your lack of faith... disturbing." - Darth Vader
"I have a bad feeling about this..." - All of the Star Wars characters.
Can I upgrade my Hard Drive to a WARP drive?
Canadian DOS prompt: EH?\\>
Canadian DOS: "Yer sure, eh?" [y/n]
CONGRESS.SYS Corrupted: Re-boot Washington D.C (Y/n)?
I don't have a solution but I admire the problem.
Famous Last Words: Trust me. I know what I'm doing.
Hey Captain, I just created a black ho-÷p!%$û NO CARRIER
Access denied. Nah nah na nah nah!
Bad command. Bad, bad command! Sit! Stay! Staaay..
Error: Keyboard not attached. Press F1 to continue.
*grumble* "You're just supposed to sit here?"
"Hey, what's this button d...<BOOM>" -W. Crusher
"He has become One with Himself!" "He's passed out!" "That too." - B5
For a funny quote, call back later.
Famous last words: 'You saw a WHAT around the corner?!'
I like work... I can sit and watch it for hours.
Copywight 1994 Elmer Fudd. All wights wesewved.
Cannot find REALITY.SYS. Universe halted.
BUFFERS=20 FILES=15 2nd down, 4th quarter, 5 yards to go!
My software never has bugs. It just develops random features.
Why doesn't DOS ever say 'EXCELLENT command or filename'?!
Shell to DOS... Come in, DOS, do you copy? Shell to DOS...
Computing Definition - Network-Admin: Primary person who just got set up for the blame of the system crash.
An expert is a person who has made all the mistakes which can be made in a very narrow field.
Famous last words: This is the safe way to do it...
Famous Last Words: Trust me. I know what I'm doing.
Clinton, "I didn't say that - er, well - yes, but I didn't mean..."
CLINTON LEGACY? Even Pharaoh had only ten plagues...
IBM             I Bought McIntosh
IBM             I Bring Manuals
IBM             I've Been Moved
IBM             Idolized By Management
IBM             Impenetrable Brain Matter
IBM             Imperialism By Marketing
IBM             Incorrigible Boisterous Mammoth
IBM             Inertia Breeds Mediocrity
IBM             Ingenuity Becomes Mysterious
IBM             Ingrained Batch Mentality
IBM             Innovation By Management
IBM             Insipid Belligerent Mossbacks
IBM             Insipidly Bankrolling Millions
IBM             Inspect Before Multiusing
IBM             Install Bigger Memory
IBM             Institution By Machiavelli
IBM             Insultingly Boring Merchandisers
IBM             Intellectuals Being Moronized
IBM             Intelligence Belittling Meaning
IBM             Intimidated, Buffaloed Management
IBM             Into Building Money
IBM             Intolerant of Beards & Moustaches
IBM             Invest Before Multi-tasking
IBM             Investigate Baffling Malodor
IBM             Irresponsible Behave Multinational
IBM             It Beats Mattel
IBM             It's a Big Mess
IBM             It's Better Manually
IBM             Itty Bitty Machine
IBM             Institute for Black Magic
100,000 lemmings can't be wrong.
Murphy's Eighth Law: If everything seems to be going well, you have obviously overlooked something.
Rules of the game: Do not believe in miracles - rely on them.
Rules of the game: Any given program, once running, is obsolete.
Computing Definition - Error: What someone else has made when they disagree with your computer output.
Backup not found: (A)bort (R)etry (P)anic
WinErr 653: Multitasking attempted - system confused.
Cannot join #real_life (invite only)
"Unfortunately, no one can be told what the Matrix is. You have to see it for yourself." - Matrix
"Reality is a thing of the past." - Matrix
"The future will not be user friendly." - Matrix
"The general idea in chat is to make yourself understandable..." - Peer
"heh i am talkin to someone... she's not dead... yet, anyways" - Stinky
"He who must die, must die in the dark, even though he sells candles."
"If at first you don't succeed, skydiving is not for you."
"Friendship is like peeing on yourself: everyone can see it, but only you get the warm feeling that it brings."
"France sucks, but Paris swallows."
"A computer once beat me at chess, but it was no match for me at kick boxing."
"Ever wonder why the SAME PEOPLE make up ALL the conspiracy theories?"
"Don't think of it as being outnumbered. Think of it as having a wide target selection."
"Sysadmins can't be sued for malpractice, but surgeons don't have to deal with patients who install new versions of their own innards."
"FACE!"
"Dirka Dirka Mohammed JIHAD!"
We can learn much from wise words, little from wisecracks, and less from wise guys.
"Blessed are the young, for they shall inherit the national debt." - Herbert Hoover
If you have five dollars and Chuck Norris has five dollars, Chuck Norris has more money than you.
Apple pays Chuck Norris 99 cents every time he listens to a song.
Chuck Norris can sneeze with his eyes open.
Chuck Norris can kill two stones with one bird.
There is no theory of evolution. Just a list of animals Chuck Norris allows to live.
The Great Wall of China was originally created to keep Chuck Norris out. It failed miserably.
Chuck Norris can win a game of Connect Four in only three moves.
Chuck Norris is not hung like a horse... horses are hung like Chuck Norris.
Chuck Norris is currently suing NBC, claiming Law and Order are trademarked names for his left and right legs.
Chuck Norris CAN believe it's not butter.
Chuck Norris is so fast, he can run around the world and punch himself in the back of the head.
When the Boogeyman goes to sleep every night, he checks his closet for Chuck Norris.
Outer space exists because it's afraid to be on the same planet with Chuck Norris.
Chuck Norris counted to infinity - twice.
Chuck Norris CAN punch you in the face over the internet.
A developer only classifies oneself as such if they consider themselves as such.
"While hunting in Africa, I shot an elephant in my pajamas. How an elephant got into my pajamas I'll never know." - Groucho Marx"""

# noinspection LongLine
# @formatter:off
ext_quotes = """The cloud is just someone else's computer that's also on fire.
DNS issue: Definitely Not Solvable issue.
JavaScript: Where '0 == []' is true but '0 == {}' is false. Perfectly logical.
Git commit message: 'I have no idea why this works but it fixed the bug.'
Debugging is like being the detective in a crime movie where you are also the murderer.
Machine Learning: The art of programming a computer to make expensive mistakes faster than a human can.
sudo make me a sandwich
The 'S' in IoT stands for Security.
My code doesn't work, I have no idea why. My code works, I have no idea why.
Docker: Because 'it works on my machine' should be everyone's problem.
404: Humor Not Found.
There are 10 types of people in the world: those who understand binary, those who don't, and those who weren't expecting a base-3 joke.
I don't always test my code, but when I do, I do it in production.
Your password must contain one uppercase letter, one number, one special character, one emoji, one drop of blood, and the soul of your firstborn.
Relationship status: Committed on main branch.
Stack Overflow: Copy and paste with extra steps.
GitHub Copilot is like pair programming, except your pair is possessed by the ghosts of all StackOverflow posts.
Zoom is just a meeting that could have been an email with extra steps.
NFTs are just digital Beanie Babies.
Web3 is a solution looking for a problem, with blockchain as its hammer and everything looking like a nail.
IRC: Where AFK actually means "typing with one hand"
Channel mode +m: When an op finally gets tired of your nonsense.
User has quit (Excess Flood): The IRC equivalent of talking too much at a party.
/ignore: The original block button.
You don't know true power until you've been a channel op during a net split.
ChanServ is the only bot that doesn't need to pass a CAPTCHA.
IRC is where people go to be alone together.
Nobody knows you're a dog on IRC, but everyone assumes you are.
The most common message in #linux: "How do I install Windows?"
IRC support in a nutshell: "I'm having a problem" "What's the problem?" "It's not working"
The three certainties in life: death, taxes, and someone asking "any girls here?" in a tech channel.
Ping timeout: The "Irish goodbye" of the internet.
IRC: Where "BRB" means anywhere from 30 seconds to 7 years.
Channel mode +b *!*@*: The nuclear option.
IRC Bots: Making sure your channel is never truly empty since 1988.
Five stages of IRC grief: join, ask, wait, rage quit, rejoin with a different nick.
Using ALL CAPS in IRC is like bringing a megaphone to a library.
"A/S/L?" - The original data mining operation.
Every IRC channel has exactly one topic: whatever the last person who spoke decided it was.
Network split: Nature's way of telling IRC users to go outside.
"This channel is dead" - Posted in a channel with 200 idle users.
NickServ: The OG of "your password must be changed every 90 days".
IRC Operators: Digital gods with internet connection problems.
The IRC paradox: Nobody responds until you say "nevermind, fixed it."
If you type your password in IRC, it automatically appears as ******** to everyone else.
"Don't make me +q you" - IRC parent energy.
IRC: Where lag is measured in decades, not milliseconds.
You haven't experienced true chaos until you've been in an IRC channel during a bot war.
In the beginning, there was darkness. Then someone typed /LIST and crashed their client.
IRC client crash messages are just advanced away messages.
IRC highlight notifications: The original dopamine hit.
Channel registration expired: The digital equivalent of someone stealing your favorite bar stool.
/me action text: The original third-person humble brag.
The most active IRC user in every channel is the one who just announced they're leaving forever.
"Guys, I found this cool new chat platform called Discord" - Words that make IRC ops cry.
AI is like a toddler: impressively smart right until you need it to recognize a school bus.
Blockchain developers: people who found a way to give a database a PR team.
An AI walks into a bar. It couldn't handle it because the bar was lower than expected.
DevOps is just sysadmin with a liberal arts degree.
CSS: Where "!important" is the digital equivalent of shouting to win an argument.
Agile development: The art of replacing one big unmeetable deadline with many small unmeetable deadlines.
If you think nobody cares if you're alive, try missing a few payments on your server costs.
Cryptocurrency mining: Because heating your house with money directly is too mainstream.
API documentation writers and sasquatch share one thing: both are rumored to exist.
Unix philosophy: Do one thing and do it well. Microsoft philosophy: Do everything and do it awkwardly.
Frontend devs and backend devs are like cats and dogs who somehow built the internet.
The "P" in PHP stands for "Performance" - oh wait...
"It's not a bug, it's an undocumented security feature."
Technical debt is like wet clothes - the longer you leave it, the more it starts to smell.
AI ethics committees exist to make sure AI doesn't become too ethical for capitalism.
"This meeting could have been a Slack message" is just "This Slack message could have been an email" with a bigger salary.
Good code is like a good joke: if you have to explain it, it's bad.
My daily routine: 1% coding, 99% explaining why I'm not done coding.
The modern IT security model: "Look ma, no hands... or encryption."
VPN: Very Pathetic Network... until the IT admin starts monitoring traffic.
IRC voice privileges (+v): Because nothing says "I almost trust you" better.
IRC: Where misspellings become running jokes that never die.
JavaScript frameworks are like Pokémon - gotta catch 'em all, but you'll never use most of them.
Ah, IRC! Where "afk" means "actually still at the keyboard, just ignoring you."
Your daily scrum isn't micromanagement, it's "agile accountability"... said no developer ever.
The only person who enjoys your Slack notification sound is the sadist who designed it.
/part #dating "Error: Cannot connect with real people"
DDOS: Don't Disturb Our Servers
Scrum masters are just project managers who learned to say "impediment" instead of "problem."
That's not a bug, it's a feature you're paying extra for in the enterprise edition.
Turns out my cloud storage was just a USB stick taped to a ceiling fan.
"I'm a full stack developer" - Translation: "I'm mediocre at many things."
IRC channels are like public bathrooms - avoid the ones with too many or too few people.
Your AWS bill and your existential dread have something in common: both grow when you're not looking.
SQL injection: The digital equivalent of "open sesame" for databases.
The average JavaScript program has more dependencies than your ex.
That moment when your 200-line function works and you're too scared to refactor it.
Logging into production servers is like playing with matches - harmless until it really, really isn't.
"Your webcam is off" - Corporate code for "we don't trust you're actually working."
IRC ban evasion is the original sock-puppet account.
Pair programming: When one person types and two people don't know what's going on.
One day, AI will look back at GPT-4 like we look back at dial-up internet.
QA Engineer walks into a bar. Orders a beer. Orders 0 beers. Orders 99999999999 beers. Orders a lizard. Orders -1 beers. Orders a
ueicbksjdhd.
Posting in IRC without reading backlog is like walking into a funeral and asking why everyone looks sad.
When an IRC operator says "This isn't appropriate for the channel," he means "Take your weird shit to private message like the rest of us."
"Works in my environment" is the "The dog ate my homework" of IT.
IRC: The place where nobody knows your name, but everyone has an opinion about your syntax.
Modern programming is just googling Stack Overflow with increasingly frustrated language.
JSON is just XML after it went to therapy.
Computers are like air conditioners - they stop working when you open too many Windows.
"The server is slow today" - Translation: "I'm trying to torrent the entire Marvel cinematic universe during work hours."
Opening more than 5 Chrome tabs is essentially a RAM donation program.
IT security is like trying to keep a glass of water safe in hell.
The problem with troubleshooting is that sometimes trouble shoots back.
IRC is the original "seen zone" where your message can be ignored by 100 people simultaneously.
Tech support: Have you tried turning it off and on again? Developers: Have you tried commenting it out and back in again?
Regular expressions are like a foreign language where you're never sure if you're saying "hello" or "your mother smells of elderberries."
The most dangerous phrase in software development: "I'll just make a quick fix."
If karma existed, everyone who's ever said "just use regex" would come back as a JIRA ticket.
The only difference between a junior and senior developer is knowing which StackOverflow answer to copy.
IRC bot command mistakes: When you accidentally send your banking password to 200 strangers.
The cleanest code is the code you didn't write.
Internet privacy is like unicorns - often discussed, never seen.
In IT, saying "it can't get worse" is basically a formal invitation for things to get worse.
Legacy code is just code without documentation that still somehow makes money.
Database administrators are like goalkeepers - nobody notices them until they mess up.
"We should hang out sometime" has the same energy as "I'll come back and refactor this later.
"Fuck" - The universal error code.
When the sysadmin walks in angry, it's like watching your dad come home with the belt.
The IT department: Where "Porn" is a network traffic category, not a moral judgment.
Typing with Caps Lock on is like shouting with your pants down - nobody takes you seriously.
Penetration testing: The only job where "I got in" is considered good news.
Hard drive failure: Nature's way of saying "you should've backed that shit up."
Two bytes walk into a bar. The bartender asks "Can I get you anything?" One byte says "Yeah, just a bit."
Roses are #FF0000, violets are #0000FF, all my code is fucked up, and so are you.
"Fucking Windows" - not sexual advice, just the universal troubleshooting phrase.
Server room: Where the air is cold and the language is colorful.
"What the fuck did you do to the DNS server?" - The IT version of "Who ate my leftovers?"
IRC kick messages are like digital tramp stamps - the more creative, the more concerning.
"Your firewall is like a condom with holes in it" - Security audit, summarized.
IT acronyms: Profanity For Beginners™
90% of IT security breaches start with "Hold my beer and watch this shit."
Sometimes I want to grep -r "fuckup" / just to find myself.
Backend developers: Doing all the hard shit while the frontend gets all the credit.
How many programmers does it take to change a lightbulb? None, that's a fucking hardware problem.
IRC: Where "ASL" is either "Age/Sex/Location" or "American Sign Language" depending on how horny the channel is.
"This shit's not working" - The most common ticket description in existence.
Testing in production is like unprotected sex - exciting at first, but you're fucked in the long run.
It's only "UDP sexual harassment" if they can prove you sent it.
Recursion: See "Recursion," you stupid motherfucker.
What the customer wanted !== what the customer paid for !== what the customer got
"Why the fuck isn't this working?!" - Most common line in code comments.
The cloud is just God's computer, and he's running low on RAM.
Your code is like your genitals - wash it regularly and don't show it to strangers without consent.
Sysadmins don't die, they just go offline permanently.
HTTP 418: I'm a teapot. HTTP 420: Enhance your calm. HTTP 666: HOLY SHIT EVERYTHING IS ON FIRE.
IRC: Where the "F" in "RTFM" stands exactly for what you think it does.
"rm -rf /" is just Linux for "fuck this shit, I'm out."
The stages of debugging: 1) What? 2) Why? 3) How? 4) Fuck it.
"It's not a memory leak, it's a surprise garbage collection opportunity."
Machine Learning: Teaching computers to learn when humans are too fucking lazy to program them.
IRC is like a digital bar where everyone's shitfaced but typing perfectly.
Backdoor exploit: The only situation where "surprise anal" is a professional term.
"Don't touch my fucking server" - The sysadmin's wedding vows.
Java developers can't change lightbulbs - they just declare darkness as the new standard.
Your password complexity is inversely proportional to how badly you need to get in.
DDoS attackers are just people who never learned to share their fucking toys.
IRC: Proving since 1988 that anonymity + audience = assholery.
"Works on my machine" is Italian for "not my fucking problem."
It's not DNS. There's no way it's DNS. It was DNS. Fuck!
"PEBKAC" - Problem Exists Between Keyboard And Chair (you're the fucking problem).
"It's a hardware issue" - Translation: "I'm too lazy to debug this shit."
Every successful backup is preceded by "oh shit oh shit oh shit."
Cryptography: Because "just trust me bro" doesn't work in security.
Fatal Error: Keyboard not detected. Press F1 to continue. Seriously, fuck you.
We didn't lose your data, we just gave it a more distributed existence.
Turning it off and on again is IT's version of "thoughts and prayers."
"Undefined is not a function" is JavaScript for "you're fucked and I won't tell you why."
Hardware techs know all the best swear words because they've hit their knuckles on everything.
Your database is like your sex life - one bad injection and you're fucked.
IRC rage quits are the digital equivalent of flipping a table and storming out.
The "B" in BSOD stands for "Buttfucked."
My favorite HTTP status code is 418: I'm a teapot, short and stout, here is my handle, fuck you.
SQL injection is just digital diarrhea - it goes where it shouldn't and ruins everything.
"Read the fucking documentation" - Four words that solve 90% of IT issues.
IRC is the only place where a grown adult can type "uwu what's this?" and not be immediately arrested.
Programming is 10% science, 20% ingenuity, and 70% getting the syntax right the first fucking time.
"sudo make me a sandwich" is just kitchen BDSM for nerds.
Two things are infinite: human stupidity and the number of browser tabs developers have open.
The printer isn't working because it's sensing your fucking fear.
IRC ban speedruns: The original toxic masculinity benchmark.
Your code is so bad it makes Windows Vista look like a masterpiece.
Computer crashes are like orgasms - always happening at the worst possible time.
"Have you tried turning it off and on again?" - The IT equivalent of "thoughts and prayers."
A clean desk is a sign of a sick mind, a clean computer is a sign of a sick hard drive.
"It's not a bug, it's undocumented foreplay with the server."
IRC channels are like toilets - the more people have been there, the less you want to touch anything.
Software development is like sex: One mistake and you have to support it for a lifetime.
The Linux command to fix all problems: rm -rf /bin/laden
IRC operators are like Unix permissions - restrictive until someone finds the sudo password.
Bash script reviews are just an elaborate way to say "what the hell were you thinking?"
"Gentoo? More like Gent-screw-you and your next 48 hours."
The terminal doesn't judge you for what you type, but your bash history certainly does.
Linux is free if your time, sanity, and will to live are worthless.
Man pages are like strip clubs - you go in looking for one thing but get distracted by all the other options.
Arch Linux users are the vegans of the computing world - they'll tell you within 30 seconds.
When a programmer says "elegant solution," they mean "this shit barely works but looks fancy."
IRC users aren't antisocial; they just prefer their rejection in text form.
The best thing about programming is that it's a socially acceptable way to be both drunk and precise.
Linux: Because fuck you, that's why.
"Permission denied" - Linux for "nice try, asshole."
vi vs. emacs is just the nerd version of Bloods vs. Crips.
IRC voice is like a digital participation trophy for people who haven't fucked up yet.
Sockets are like toilets - everyone uses them but nobody wants to know how they work.
chmod 777: For when you absolutely, positively don't give a fuck about security.
Linux users don't die, they just get a kernel panic.
The C programming language: Where "segmentation fault" is just another way to say "go fuck yourself."
IRCops: Digital dictators with god complexes and poor social skills.
A UNIX tarball is like a digital STD - you never know what you'll get when you extract it.
Bash scripting is just programming with extra swearing.
Your terminal history reveals more about you than your browser history.
"Unexpected token" is JavaScript's way of saying "that's not what I fucking wanted."
IPv6 adoption is like sex in your 30s - you know you should be doing it more often, but it's just too much effort.
The best feature of vi is that it keeps the interns away from your codebase.
IRC: The original "fuck around and find out" of the internet.
"Core dumped" is just UNIX for "shit the bed."
The Linux filesystem hierarchy is like a family tree in Alabama - everything is related and nothing makes sense.
Programming languages are like sex partners - everyone has their favorite but they're all frustrating in different ways.
"No route to host" is networking for "go home, you're drunk."
Linux command line: Where men are men, women are men, and children are FBI agents.
Your IRC client is the digital equivalent of your bedroom - messy, full of scripts you don't understand, and nobody else should ever see it.
"I don't care if it's standards-compliant; does the damn thing work or not?"
Perl: The only language that looks the same before and after RSA encryption.
IRC networks are like dysfunctional families - lots of drama, frequent splits, and nobody talks to each other.
Pointers in C: The programming equivalent of giving a toddler a loaded gun.
Kernel panics are just Linux's way of saying "I can't even."
God created the integers, all else is the work of woman. Segmentation fault - core dumped.
IRC services are like bouncers at a club - they exist solely to make you feel bad about forgetting your password.
The Linux learning curve isn't a curve, it's a fucking wall with spikes on top.
Writing Bash scripts is like being an abusive parent - lots of yelling and unexpected behavior.
IRC: Where people with social anxiety go to practice having social anxiety.
A programmer had a problem. They thought, "I know, I'll solve it with threads!" have Now two problems. they.
Real programmers don't comment their code. If it was hard to write, it should be hard to understand.
The most dangerous Linux command isn't rm -rf /; it's giving an intern sudo access.
"READ. THE. FUCKING. MANUAL." - The Linux community's entire approach to customer service.
Channel modes are like condoms - if you don't use them properly, you'll end up with unwanted visitors.
Your terminal is like your genitals - customizable, frequently abused, and nobody wants to see what you've done with it.
There are two hard problems in computer science: cache invalidation, naming things, and off-by-one errors.
Telling someone to RTFM in IRC is like telling someone who's drowning to learn how to swim.
chmod 000 /: For when you absolutely, positively hate everyone, including yourself.
Every Linux distro is just Ubuntu with a different hat and an attitude problem.
IRC networks go down more often than a $2 hooker.
Segmentation Fault: C's way of saying "I don't know what the fuck happened, but it's your fault."
Linux distros are like assholes - everyone has one, they all stink, and nobody wants to look at anyone else's.
Programming is just telling a rock it's stupid in increasingly complex ways.
"It's just a one-line fix" - Famous last words before the all-night debugging session.
Watching IRC network drama unfold is like seeing monkeys throw shit at each other at the zoo.
The best part of being a sysadmin is having the power to kick anyone who asks for help.
IRC is like a sword fight - the goal is to remain connected while making everyone else disconnect.
Python package management is proof that programmers shouldn't be allowed to design anything.
"Hotfixing production at 3am" - The developer's equivalent of drunk texting an ex.
Heisenbugs: When observing the bug changes its behavior, and you want to observe the programmer's face instead.
IRC is the digital equivalent of a bar where everyone can hear everyone else but pretends not to be listening.
Linux: An operating system where you either become a god or go back to Windows crying.
Object-oriented programming is like teenage sex - everyone talks about it, nobody really knows how to do it, and the attempts are often disastrous.
The most beautiful words in IRC: "ops plz ban this fucker"
A good programmer can write FORTRAN in any language. A great programmer can write any language in PERL.
Sysadmins don't die, they just sudo killall -9.
IRC server splits are the original "Dad went out for cigarettes and never came back."
If programming is like sex, then Lisp is like masturbation - it's more fun when you add parentheses.
Linux users treat Windows users the way Jehovah's Witnesses treat the unsaved.
The most efficient debugging tool is still a good old-fashioned printout of "What the fuck am I here?"
"All systems are working normally" - The DevOps equivalent of "This is fine" while everything burns.
The Linux command line is just a BDSM relationship where you're the submissive.
RFC is short for "Really Fucking Complicated."
"Works on my machine" should be grounds for immediate termination.
Your code is like my sex life - it only works when nobody's watching.
Regex is like scat porn - horrifying to most, but some sick bastards claim to enjoy it.
Programming in PHP is the BDSM of web development - painful, degrading, yet oddly popular.
Linux kernel development is just digital BDSM where Linus Torvalds is the dom and you're the gimp.
IRC is where virgins congregate to discuss all the sex they're not having.
"Connection timed out" - The digital equivalent of erectile dysfunction.
Debugging multithreaded applications is like trying to fuck a porcupine - painful no matter how carefully you approach it.
"Unhandled exception" is just the computer's way of saying "you fucked up beyond my capacity to give a shit."
IRC channels about programming are just digital circle jerks where nobody comes to a conclusion.
"Garbage Collection" is what HR should do with most JavaScript developers.
IRC channel drama makes trailer park incest look like sophisticated entertainment.
Your commit history reads like the medical chart of someone with violent diarrhea - frequent, messy, and poorly documented.
Windows users masturbate with Edge. Mac users masturbate with Safari. Linux users can't masturbate because they're too busy recompiling their kernel.
Version control is like contraception - one mistake and you're supporting it for years.
Apple fanboys bend over harder for new products than prison inmates on their first night.
The only thing more penetrable than JavaScript security is your mom.
The TCP handshake is the only consensual interaction most IRC users ever experience.
React development is like anal sex - everyone's doing it but nobody admits how painful it is.
Most Linux forum answers are the intellectual equivalent of "go fuck yourself with something sharp."
Enterprise Java applications are the STDs of corporate computing - painful, persistent, and passed around by people who should know better.
IRC trolls are like digital glory holes - nobody knows or cares who's on the other side.
Blockchain is just a global bukkake of computational waste.
"Dependency hell" is the tech equivalent of finding out all your exes now fuck each other.
The difference between junior and senior devs is knowing when to say "fuck this, let's rewrite it" and when to say "fuck it, let's ship it."
Machine learning is like autoerotic asphyxiation - thrilling, dangerous, and if you go too far, you'll end up with a lifeless model.
Any sufficiently advanced code is indistinguishable from someone having a stroke on a keyboard.
Linux distro-hopping is just the tech version of a midlife crisis - constantly trying new things hoping one will finally satisfy you.
IRC channel kicks are the digital equivalent of premature ejaculation - sudden, embarrassing, and usually someone's fault.
"It compiles" means as much for code quality as "She breathes" does for relationship quality."""


def show_quote(client):
    all_quotes = (quotes + ext_quotes).split('\n')
    quote = random.choice(all_quotes)
    IRCD.server_notice(client, quote)


def init(module):
    Hook.add(Hook.LOCAL_CONNECT, show_quote)
