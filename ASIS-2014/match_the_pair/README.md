# ASIS Cyber Security Contest Finals 2014: MATCH THE PAIR

![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ASIS-2014/match_the_pair/1.png)

## The Challenge

Visiting the site http://asis-ctf.ir:12443 gives us the web game below:

![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ASIS-2014/match_the_pair/2.png)

The challenge is the match up pairs of images based on the color of the circle within the image.  Each image is a simple 180x100px .png named from 0.png to 15.png.  The site will happily dispense any png, by visiting the link: "http://asis-ctf.ir:12443/pic/<number of image>" (e.g. "http://asis-ctf.ir:12443/pic/0").  The colors of the circles are not always exact matches and in some cases may be very different shades of the same color.

Below is an example png:

![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ASIS-2014/match_the_pair/3-0.png)

The game starts at level1 and you must navigate 40 levels of matching to claim the flag.  The amount of time available is limted for each level, so it is impossible to win by hand (although you can make it through the first level easy enough).  When a player attempts to complete matches the results are sent as an HTTP GET request like below:

```bash
http://asis-ctf.ir:12443/send?first=0&second=1
```

The site responds with the results of your attempted match.  If you are correct it responds with "ok", if not "f", "e" if you make some kind of mistake, or "done" if you have completed the level.  If you have completed all 40 levels the site will respond with "Go \/flag" which means to visit http://asis-ctf.ir:12443/flag to claim the flag.

Finally, the site maintains state using a session cookie that changed names during the competition.  Originally the cookie was named "sessionid" but later changed to "PHPSESSID".

## The Solution

For this challenge I went with python and opencv.  Opencv allows detection of shapes within images.  Specifically it allows the use of Hough Circle Transforms to find circles in images.  You can read more about this here:

```bash
http://docs.opencv.org/doc/tutorials/imgproc/imgtrans/hough_circle/hough_circle.html
```

The flow of the solution looks like this...

```bash
1. Create a session with the site, grabbing the session ID.
2. Grab all 16 images for the current level
3. Find the circles in all 16 images
4. Find the color of the circle
5. Compare the images to find which ones are the closest match
6. Send 8 GET requests completing the matches
7. Go to 2. and repeat for the next level until we get to level 40
8. Go to /flag and get the flag.
```

The source code for my solution can be found here:

```bash
https://github.com/psmitty7373/ctf-writeups/blob/master/ASIS-2014/match_the_pair/circles.py
```

However, I wanted to talk about a few idosyncrasies with solving the problem.

1. The solutions must be completed fast!  This required that I pull all 16 images asycronously.  I used python threads and grabbed them all at the same time.
```python
def getpic(i, cookie):
        req = urllib2.Request('http://asis-ctf.ir:12443/pic/' + str(i))
        req.add_header('User-agent', 'Mozilla/5.0 (Windows NT 5.1; rv:31.0) Gecko/20100101 Firefox/31.0')
        req.add_header('Cookie',cookie)
        resp = urllib2.urlopen(req)
        imgData = resp.read()
        o = open('pics\\' + str(i) + '.png','wb+')
        o.write(imgData)
        o.close()

for i in range(0,16):
    t = Thread(target=getpic, args=(i,cookie))
    t.start()
    threads.append(t)
for i in threads:
    i.join()
```    
2. Opencv had issues finding the circles at times.  The line that actually finds the circles is below:
```python
circles = cv2.HoughCircles(gray, cv2.cv.CV_HOUGH_GRADIENT, 1, 20, param1=50, param2=15, minRadius=0,maxRadius=0)
```
I had to manipulate the param2 quite a bit to finally get it to reliably find the circles.  An explanation of those parameters can be found here:
```bash
http://docs.opencv.org/modules/imgproc/doc/feature_detection.html?highlight=houghcircles#houghcircles
```
Here you can see where opencv struggled a little to find the image... but was good enough!
![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ASIS-2014/match_the_pair/1out.png)


And here opencv was right on...

![alt tag](https://raw.githubusercontent.com/psmitty7373/ctf-writeups/master/ASIS-2014/match_the_pair/pics/3out.png)


3. The colors were never exact... sometimes the were quite different.  I discovered that you had to find the "closest" match.  I did this by comparing RGB values and finding how different each circle was.  I didn't do this the best way, but it worked:
```bash
dist = abs(int(i[1]) - int(j[1])) + abs(int(i[2]) - int(j[2])) + abs(int(i[3]) - int(j[3]))
```
4. Once the 8 closest matches were found and (with duplicates eliminated).  I found that they had to be submitted very rapidly.  If you did them sequentially, you would run out of time and the server would return "slow" and send you back to level 1.  To get around this, I had to send all 8 matches at the same time.
```python
def sendmatches(a,b,cookie):
        req = urllib2.Request('http://asis-ctf.ir:12443/send?first=' + str(a) + '&second=' + str(b))
        req.add_header('User-agent', 'Mozilla/5.0 (Windows NT 5.1; rv:31.0) Gecko/20100101 Firefox/31.0')
        req.add_header('Cookie',cookie)
        resp = urllib2.urlopen(req)
        respData = resp.read()
        print respData
        if respData == '"ok"':
            print 'MATCH!'
        elif respData == '"f"':
            print 'Error!  Invalid match... trying next one..'
        else:
            print respData
            
for i in matches[:8]:
    t = Thread(target=sendmatches, args=(i[0],i[1],cookie))
    t.start()
    threads.append(t)
for i in threads:
    i.join()
```
5. Once the code was working, I just let it plow through 40 levels hoping for the best.  Once the code hit level 40, I saw instead of "done" the server returned "Go \/flag".  Visiting the site with the same session id gives us the flag:
```bash
ASIS_28ca740e382225131fc0501d38cf5d30
```

