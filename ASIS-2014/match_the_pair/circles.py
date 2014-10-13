import cv2
import cv2.cv as cv
import numpy as np
import urllib2
import time, sys
from threading import Thread

req = urllib2.Request('http://asis-ctf.ir:12443/')
req.add_header('User-agent', 'Mozilla/5.0 (Windows NT 5.1; rv:31.0) Gecko/20100101 Firefox/31.0')
resp = urllib2.urlopen(req)
data = resp.read()
headers = resp.info()
cookie = headers['Set-Cookie'].split(';')[0]
print 'Cookie!: ' + cookie
first = True
done = False

def getpic(i, cookie):
        req = urllib2.Request('http://asis-ctf.ir:12443/pic/' + str(i))
        req.add_header('User-agent', 'Mozilla/5.0 (Windows NT 5.1; rv:31.0) Gecko/20100101 Firefox/31.0')
        req.add_header('Cookie',cookie)
        resp = urllib2.urlopen(req)
        imgData = resp.read()
        o = open('pics\\' + str(i) + '.png','wb+')
        o.write(imgData)
        o.close()

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
        elif respData == '"done"':
            done = True
        else:
            print respData
            
for k in range(0,45):
    if not first:
        req = urllib2.Request('http://asis-ctf.ir:12443/')
        req.add_header('User-agent', 'Mozilla/5.0 (Windows NT 5.1; rv:31.0) Gecko/20100101 Firefox/31.0')
        req.add_header('Cookie',cookie)
        resp = urllib2.urlopen(req)
        print resp.read()
        #sys.exit(0)
    first = False
    colors = []
    threads = []
    for i in range(0,16):
        t = Thread(target=getpic, args=(i,cookie))
        t.start()
        threads.append(t)

    for i in threads:
        i.join()

    for i in range(0,16):
        image = cv2.imread('pics\\' + str(i) + '.png')
        if image.data == None:
            print 'Error loading image'
        output = image.copy()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # detect circles in the image
        circles = cv2.HoughCircles(gray, cv2.cv.CV_HOUGH_GRADIENT, 1, 20, param1=50, param2=15, minRadius=0,maxRadius=0)
         
        # ensure at least some circles were found
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            for (x, y, r) in circles:
                print str(i) + ': ' + str(image[y,x,2]) + ',' + str(image[y,x,1]) + ',' + str(image[y,x,0])
                colors.append((i, image[y,x,2], image[y,x,1], image[y,x,0]))
                cv2.circle(output, (x, y), r, (0, 255, 0), 4)
                cv2.rectangle(output, (x - 5, y - 5), (x + 5, y + 5), (0, 128, 255), -1)
                i += 1
                break
            #cv2.imshow("output", np.hstack([image, output]))
            #cv2.waitKey(0)
        else:
            print 'ERROR! No circles!'
            sys.exit(1)

    done = False
    matches = []
    for i in colors:
        for j in colors:
            dist = abs(int(i[1]) - int(j[1])) + abs(int(i[2]) - int(j[2])) + abs(int(i[3]) - int(j[3]))
            temptup = []
            if (i[0] < j[0]):
                temptup = ((i[0],j[0],dist))
            elif (i[0] > j[0]):
                temptup = ((j[0],i[0],dist))
                try:
                    pos = matches.index(temptup)
                except:
                    pos = -1
                if pos == -1:
                    matches.append((j[0],i[0],dist))
    matches = sorted(matches, key=lambda tup: tup[2])
    threads = []
    for i in matches[:8]:
        t = Thread(target=sendmatches, args=(i[0],i[1],cookie))
        t.start()
        threads.append(t)
    for i in threads:
        i.join()
