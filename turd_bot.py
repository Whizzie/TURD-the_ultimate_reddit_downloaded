#!/usr/bin/env python
import datetime
from time import time
import re, praw, requests, os, glob, sys, lxml, getopt, httplib, urllib2
from bs4 import BeautifulSoup
from termcolor import colored
import MySQLdb as mdb
from PIL import Image
from multiprocessing import Pool
from time import gmtime, strftime
from secrets import reddituser, redditpass, sql_user, sql_pass, sql_db
import shutil
from urlparse import urlparse
from imgurpython import ImgurClient



# set up some variables
scriptname = 'TURDs - The Ultimate Reddit Downloader - Simplified'
scriptver = '0.2'
botid = ('Favourite Saver by /u/SFD')

client = ImgurClient(client_id, client_secret)

script = os.path.dirname(os.path.abspath(__file__)) + '/'
imgurUrlPattern = re.compile(r'(http://i.imgur.com/(.*))(\?.*)?')
prepath = script + "reddit/"
l = 0
albumcleared = False

theheader = '''
    %s
              ,='~'z_           H
             / .'   `\          H
            (  /      )         H
            / /`--.._  )        H
           (  )=-  =)  |        H
            ) \  .  (_/         H
           (   \`=' /~          H
       ,--._)_/^`- ~\.__        H
      /                 ``-.    H
     /                      .   H
    /   ) ,  / , .    .     :   H
   /   / / '    ,' _   Y    :   H
  /   _Y-'   ,._;\(*)  |    |   H
 / ,-'    .-.`    \_  /|    |   H
:       ,`-  `=.._  ~'-=.   (   H
|     ,' |       `-.     `  |   H
 \__.'   |          `._     /   H
         |            |`'--'    H
         |             \        H
         /      o       \       H
        /                \      H
       J                  L     H
       [       \XXX/      |     H
       [        \X/       |     H   Version:    %s
       [        /(        |     H   Time Stamp: %s
       |       / |        F     H
       |      /  |       /      H
''' %(scriptname, scriptver, strftime("%Y-%m-%d %H:%M:%S"))

thehelp = '''
\033[1m########################

The Ultimate Reddit Downloader - Simplified [TURDs]

########################

\033[0mOptions:
  turd -h
  prints this help page

  turd.py -t
  test mode - does not delete or unsave anything.

  turd.py -s
  downloads the saved links for the user[s] saved in 'secrets.py'

  turd.py -f
  downloads the posts by user[s] in a CSV file called faves.txt

  turd.py -a [url]
  downloads an album linked to in comment [url]

  turd.py -m [redd.it url]
  manual mode download an [url] from a reddit shortcut when it gets messy.

  turd.py -r <redditor>
  this will do a quick download of everything posted by <redditor>

'''

# colors used for output
ok = 'green'
success = 'cyan'
warn = 'magenta'
info = 'yellow'
alert = 'red'

# lets make a nice clean interface to start
print script

os.system('clear')
print colored( theheader, warn)

# then we need to log in
r = praw.Reddit(user_agent = botid)
r.login(reddituser, redditpass, disable_warning=True)

#
# Below here are the subroutines for doing shit
#

#
# define the command line options
#
def options(argv):
    global testmode, process, targetAlbum, targetDir, link, redditor

    process = ''
    testmode = ''
    targetAlbum = ''
    targetDir = ''

    try:
        opts, args = getopt.getopt(argv,'ha:r:tfslm:')
    except getopt.GetoptError:
        print 'type turd.py -help for help'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print colored ('you\'re asking for help?', ok)
            print
            thehelp()
            sys.exit()
        if opt == '-t':
            testmode = True
            print colored ('!!! TEST MODE ON !!!', warn)
        if opt == '-f':
            process = 'friends'
            return
        if opt == '-l':
            process = 'fanlist'
            return
        if opt == '-s':
            process = 'saved'
            return
        if opt == '-r':
            redditor = arg
            process = 'research'
            return
        if opt == '-a':
            link = arg
            process = 'album'
        if opt == '-m':
            link = sys.argv
            process = 'manual'

#
# here we analyze each link to see what we need to do with it.
#
def analyze ():
    saved.url, null, null = saved.url.partition('#')
    saved.url, null, null = saved.url.partition('?')
    print colored('Analyzing %s' %saved.url, info)

    if saved.url.lower().endswith(('.jpg','.jpeg','.gif','.png','.webm','.gifv','.mp4')): # These are files we can download easily
        direct()
    elif "imgur.com/" in saved.url: # It's on imgur
        if ('imgur.com/a/' or 'imgur.com/gallery/') in saved.url:
            imgurAlbum()
        elif 'http://imgur.com/' or 'http://m.imgur.com' in saved.url:
            singleImage()
    else:
        non_imgur() # It's not imgur

#
# direct image links - works with most sites
#
def direct():
    print colored ('direct image link:', 'white', 'on_red') + ' ' + saved.url
    imgurFilename = saved.url.rsplit('/', 1)[1]
    if '?' in imgurFilename:
        # The regex doesn't catch a "?" at the end of the filename, so we remove it here.
        imgurFilename = imgurFilename[:imgurFilename.find('?')]
    downloadImage(saved.url, savePath, imgurFilename)
    unsave()

#
# imgur album
#
def imgurAlbum():
    print '  ' + colored ('Album: ', 'white', 'on_red') + ' ' + saved.url
    if saved.url.endswith('/all'):
        album = saved.url.rsplit('/', 1)[0]
        print colored ('    Snipped /: %s' %(album), info)
    elif '#' in saved.url:
        album = saved.url.rsplit('#', 1)[0]
        print colored ('  Snipped #: %s' %(album), info)
    else:
        album = saved.url
        print colored ('    %s' %(album), info)

    method = "1"
    matches = []

    # API method first
    albumID = album.rsplit('/', 1)[1]
    print colored ('    API Album ID: %s' %(albumID), info)

    items = client.get_album_images(albumID)

    i = 0
    for item in items:
        i = i + 1
        link = re.sub('http:', '', item.link)
        print'  API %s - %s' %(i, link)
        matches.append(link)

    if len(matches) < 1 :

        htmlSource = requests.get(album).text

        # method 1 - find any links inside class

        soup = BeautifulSoup(htmlSource)

        '''
        for x in soup.find_all('div', attrs={'class':'album-view-image-link'}):
            if a[href] is true:
                print colored ('Method 1: %s' %x.a[href], info)
                matches.append(x.a['href'])
        '''
        # method 2 - get a noscript version

        noscriptURL = album + '/noscript'
        noscriptSource = requests.get(noscriptURL).text
        soup = BeautifulSoup(noscriptSource)

        for x in soup.select('.wrapper'):
            if x.img['src'] not in matches:
                print colored('Method 2: %s' %x.img['src'], info)
                matches.append(x.img['src'])

        # method 3
        for line in htmlSource.splitlines():
            if re.search('(og:image).*(http(s?)://.*[\.jpg|\.gif|\.gifv|\.png])', line):
             #if re.search('(<img src=").*(" alt="" />)', line, re.I):
                if not re.search('i.imgur.com/.jpg', line, re.I): # remove any /.jpg files
                    theImage = re.search('(//.*[\.jpg|\.gif|\.gifv|\.png])', line, re.I).group()
                    if theImage not in matches:
                        print colored('Method 3: %s' %theImage, info)
                        matches.append(theImage)

        # method 3A
        for line in htmlSource.splitlines():
            # class="post-image-placeholder" src="
            if re.search('post-image-placeholder', line):
             #if re.search('(<img src=").*(" alt="" />)', line, re.I):
                if not re.search('i.imgur.com/.jpg', line, re.I): # remove any /.jpg files
                    theImage = re.search('(//.*[\.jpg|\.gif|\.gifv|\.png])', line, re.I).group()
                    if theImage not in matches:
                        print colored('Method 3A: %s' %theImage, info)
                        matches.append(theImage)


        # method 3B
        for line in htmlSource.splitlines():
            # class="post-image-placeholder" src="
            if re.search('zoom', line):
             #if re.search('(<img src=").*(" alt="" />)', line, re.I):
                if not re.search('i.imgur.com/.jpg', line, re.I): # remove any /.jpg files
                    theImage = re.search('(//.*[\.jpg|\.gif|\.gifv|\.png])', line, re.I).group()
                    if theImage not in matches:
                        print colored('Method 3B: %s' %theImage, info)
                        matches.append(theImage)

        # method 4 - get the grid view
        gridSource = requests.get('%s/layout/grid' %album).text
        for line in gridSource.splitlines():
            if re.search('<img alt="" src="(//*[\.jpg|\.gif|\.gifv|\.png])"', line, re.I):
                if not re.search('i.imgur.com/.jpg',line, re.I): # remove any /.jpg files
                    theImage = re.search('<img alt="" src="(//.*[\.jpg|\.gif|\.gifv|\.png])"', line, re.I).group(1)
                    if theImage not in matches:
                        theImage = re.sub('b\.', '.', theImage)
                        print colored('Method 4: %s' %theImage, info)
                        matches.append(theImage)

        # method 5
        for line in htmlSource.splitlines():
            if re.search('(<img src=").*(" alt="" />)', line, re.I):
                if not re.search('i.imgur.com/.jpg', line, re.I): # remove any /.jpg files
                    theImage = re.search('(//.*[\.jpg|\.gif|\.gifv|\.png])', line, re.I).group()
                    if theImage not in matches:
                        print colored('Method 5: %s' %theImage, info)
                        matches.append(theImage)

        # method 6
        for line in htmlSource.splitlines():
            if '"og:image"' in line:
                image = re.search(r'(?i)//.*(\.jpg|\.gif|\.gifv|\.png)', line)
                if image is not None:

                    print colored("Method 6: %s" %image.group(0), info)
                    matches.append(image.group(0))
                else:
                    print colored("......passing %s" %image, warn)
                # regular expressions are here
                # help? http://pythex.org/

        # method 7
        grid_page = page_download('%s/layout/grid' %album)
        soup = BeautifulSoup(grid_page)
        post = [i.renderContents().strip() for i in soup.findAll('div', {'class': 'post'})]
        x = 0
        for line in post:
            x = x + 1
            image = re.search(r'(?i)//.*(\.jpg|\.gif|\.gifv|\.png)', line)
            print colored("Method 7: %s" %image.group(0), info)
            matches.append(image.group(0))

    if len(matches) < 1:
        print colored('    No Links found any fucking way', warn)
        return
    else:
        print colored('Found %s images' %len(matches), info)
        
    # images found in album download
    albumSavePath = savePath + ('%s/' %(saved.id))
    print colored ('  > %s Links Found with method %s' %(len(matches), method), warn)

    for match in matches:
        if re.search('(\.jpg|\.gif|\.gifv|\.png)', match): # remove any base64 images

            if '?' in match:
                imageFile = match[match.rfind('/') + 1:match.rfind('?')]
            else:
                imageFile = match[match.rfind('/') + 1:]

            downloadImage('http:' + match, albumSavePath, imageFile)

    enfo = 'title: %s\n' %(saved.title)
    enfo = enfo + 'poster: %s\n' %(saved.author)
    enfo = enfo.encode('ascii', errors='ignore')

    if albumcleared is True:
        with open(prepath + albumSavePath + 'info.txt', 'a+') as nfo:
            nfo.write(enfo)
            print 'info file saved'

    unsave()

#
# subroutine for imgur pages with a single image
#
def singleImage():
    print colored ('single image page:', 'white', 'on_red') + ' ' + saved.url
    htmlSource = requests.get(saved.url).text # download the image's page

    if 'simple 404 page' in htmlSource:
        print colored ("404 Error", warn)
        return
    soup = BeautifulSoup(htmlSource)

    imageUrl = soup.find('meta',{"property":"og:image"})['content']
    #imageUrl = soup.select('#image img')[0]['src']
    if imageUrl.startswith('//'):           # if no schema is supplied in the url, prepend 'http:' to it
        imageUrl = 'http:' + imageUrl
        imageId = imageUrl[imageUrl.rfind('/') + 1:imageUrl.rfind('.')]

    if '?' in imageUrl:
        imageFile = imageUrl[imageUrl.rfind('/') + 1:imageUrl.rfind('?')]
    else:
        imageFile = imageUrl[imageUrl.rfind('/') + 1:]

    downloadImage(imageUrl, savePath, imageFile)
    unsave()

#
# subroutine for non-imgur links
#
def non_imgur():
    print colored ('non Imgur link:', 'white', 'on_red') + ' ' + saved.url

    # it's gfycat
    if "gfycat.com" in saved.url:
        print colored ('  Analyzing a gfycat link', info)
        saved.url = saved.url.replace('https', 'http')
        matches = []
        htmlSource = requests.get(saved.url, verify=False).text # download the album page

        for line in htmlSource.splitlines():
            if re.search('https://(.*).gfycat.com/(.*).mp4', line):
                matches.append(line)

        matched = re.search ('https://(.*).mp4', matches[1])
        imageUrl = matched.group(0)
        imageFile = imageUrl.rsplit('/',1)[1]

        print colored ('    found %s' %imageFile, info)
        downloadImage(imageUrl, savePath, imageFile)
        unsave()


        '''            if (re.search('gfyMp4Url', line) or
                re.search('mp4URL', line) or
                re.search('mp4Source', line)
               ):

                imageUrl = re.search('http.*mp4',line).group(0)
                imageFile = saved.url.rsplit('/', 1)[1]


            else:
                print colored ("Trying method 2", info)
                imageFile = saved.url.rsplit('/', 1)[1]
                imageUrl = 'https://giant.gfycat.com/%s.mp4' %imageFile
                
                print colored ('    found %s' %imageFile, info)
                downloadImage(imageUrl, savePath, imageFile)
        '''
                

    #it's a redirect back to reddit
    elif '://www.reddit.com' in saved.url:
        print colored ('The old reddit swich-a-roo', info)
        return()

    #it's a vidible album
    elif re.search('vidble.com', saved.url):

        print colored ('vidble album', info)
        htmlSource = requests.get(saved.url).text # download the album page

        soup = BeautifulSoup(htmlSource)

        matches =[]

        for img in soup.find_all('img', attrs={'class':'img2'}):
            if img.get('src') is not None:
                matches.append('//vidble.com' + img.get('src'))

        albumSavePath = savePath + ('%s/' %(saved.id))
        print colored ('  > %s Links Found' %len(matches), warn)

        for match in matches:
            if '?' in match:
                imageFile = match[match.rfind('/') + 1:match.rfind('?')]
            else:
                imageFile = match[match.rfind('/') + 1:]
            downloadImage('http:' + match, albumSavePath, imageFile)

        enfo = 'title: %s\n' %(saved.title)
        enfo = enfo + 'poster: %s\n' %(saved.author)
        enfo = enfo.encode('ascii', errors='ignore')

        with open(prepath + albumSavePath + 'info.txt', 'a+') as nfo:
            nfo.write(enfo)
            print 'info file saved'
            unsave()

    #eroshare code here
    elif 'eroshare' in saved.url:
        print colored ('eroshare', info)

        htmlSource = requests.get(saved.url, verify=False).text # download the page
        matches = []

        for line in htmlSource.splitlines():
            if re.search('https://(.*).mp4', line):
                matches.append(line)
                print colored ('%s %s' %(l, line), success)

        if matches.count > 1:
            albumSavePath = savePath + ('%s/' %(saved.id))
            print 'AlbumSavePath = %s' %albumSavePath

            for match in matches:
                print 'match = %s' %match
                url = re.findall ('src="(.*)" type', match)
                if len(url) > 0:
                    print 'URL = %s' %url[0]

                    imageFile = url[0].split('/')[-1]
                    print 'imageFile = %s' %imageFile

                    downloadImage(url[0], albumSavePath, imageFile)

            unsave()

    else:
        print colored ('    Skipping - can\'t extract from: ' + saved.url, warn)
        
def page_download(url):
    print colored('Downloading Page: %s' %url, info)
    try:
        headers = {
            "Accept" : "text/html",
            "User-Agent" : "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.11; rv:44.0) Gecko/20100101 Firefox/44.0"
        }
        request = urllib2.Request(url, headers=headers)
        return urllib2.urlopen(request).read()
    except urllib2.HTTPError, e:
        exit()
    except urllib2.URLError, e:
        exit()        

#
# subroutine that actually downloads the file[s] and saves it/them
#
def downloadImage(imageUrl ,path , localFileName):
    # imageURL = the URL of the source image
    # path = the path to save the file to
    # localFileName = the name to save the file with

    # remove any question marks and everything after
    if '?' in imageUrl:
        NewimageUrl = imageUrl.split('?')
        imageUrl = NewimageUrl[0]
        print colored ('split imageURL %s' %(imageUrl), info)
    if '?' in localFileName:
        NewlocalFileName = localFileName.split('?')
        print colored('split localFileName %s' %(localFileName), info)
        localFileName = NewlocalFileName[0]

    if imageUrl.lower().endswith('.gifv'):
        imageUrl = imageUrl.replace('.gifv', '.mp4')
        localFileName = localFileName.replace('.gifv', '.mp4')
        print colored('    swapped .gifv to download .mp4')

    path = prepath + path
    path = path.encode('ascii', errors='ignore')
    print colored('dl > ', 'grey', 'on_green'),
    print colored('%s' %(imageUrl), info),

    if 'logo-1200-630.jpg' in imageUrl:
        print colored('Album Cleared :o %s' %(imageUrl), warn)
        albumcleared = True
        return

    if os.path.isfile(path + localFileName):
        print colored ('File exists', 'white', 'on_blue')
        if not os.path.isfile(path + '_thumbs/' + localFileName):
            if localFileName.endswith(('.jpg', '.gif')):
                thumb (path, localFileName)
        return

    # make the directory if it does not exists already
    if not os.path.exists(path):
        os.makedirs(path, 0777)

    # make the thumbs directory too
    if not os.path.exists(path + '/_thumbs/'):
        os.makedirs(path + '/_thumbs/')
        os.chmod(path+ '/_thumbs', 0777)

    # get the file
    response = requests.get(imageUrl)
    if response.status_code == 200:
        filesize = response.headers['content-length']
        if int(filesize) <= 600:
            print colored('File Gone :( %s' %(filesize), warn)
        else:
            print colored ('    Saving %s B... ' % (filesize), ok)
            #cur.execute (sqlsave,(saved.id, saved.title, saved.author, saved.url, targetSubreddit, saved.id))
            with open(path + localFileName, 'wb') as fo:
                for chunk in response.iter_content(4096):
                    fo.write(chunk)
                os.chmod(path + localFileName, 0666)
            if localFileName.lower().endswith(('.jpg', '.gif', '.png')):
                thumb(path, localFileName)
            print ' '
    else:
        print colored ('File Not Found', warn)
        return

#
# create the thumbnails
#
def thumb(path, filename):
    thumbsize = (125,125)
    im = Image.open(path + filename)
    width, height = im.size
    try:
        im.thumbnail( thumbsize )
        im.save( path + '_thumbs/' + filename, "JPEG")
        print colored('tn > ', 'grey', 'on_magenta'),
        print colored ('%s' %(path + '_thumbs/' + filename), info)
    except Exception as e:
        print e

#
# delete from saved
#
def unsave():
    if testmode is not True:
        date_now = datetime.date.today()
        date_created = datetime.date.fromtimestamp(saved.created) # .strftime('%Y-%m-%d')

        date_delta = date_now - date_created

        if date_delta.days < 150:
            saved.upvote()
            print colored ('    Upvoted: ' + saved.title, success)
        else:
            print colored ('    Can\'t Upvote: %s days old' %date_delta.days, success)
        saved.unsave()
    else:
        print colored ('    Not Unsaved: ' + saved.title, success)

#
# ^^^
#
# All functions above this line
#
# ---
#
# Below here we do the process and act on it
#
# vvv
#

if __name__ == "__main__":
   options(sys.argv[1:])
   l = 0
   saved = []

if process == 'saved':
    print colored ('Downloading saved links', info)

    for saved in r.user.get_saved(limit=150):
        l = l + 1
        print
        print '-----------------'
        print ('%s. Analyzing: ' %(l))

        if type(saved) == praw.objects.Submission:
            print colored('  %s' %(saved.title), 'yellow')
            print colored('  %s' %(saved.author), 'yellow')

            # define the target subreddit for when we create the directories
            targetSubreddit = saved.subreddit
            targetAuthor = saved.author

            savePath = '%s/%s/' % (targetSubreddit, targetAuthor)

            analyze()

            print 

elif process == 'fanlist':
    print colored ('Downloading favorite posters', info)

    #shutil.copyfile(script +'faves.txt', script + 'reddit/faves.txt')

    with open(script + 'faves.txt', 'r') as f:
        targets = [line.strip() for line in f]

    for line in targets:

        target, depth = line.split(',')

        if '---quit---' in target:
            exit()
        else:
            print colored('T: %s [%s]' %(target, depth), success),

        # check user is still active
        conn = httplib.HTTPConnection('reddit.com')
        conn.request("HEAD", '/u/%s' %(target))
        response = conn.getresponse().status
        print colored (response, alert)

        ruser = r.get_redditor(target)

        l = 0

        for saved in ruser.get_submitted(limit=int(depth)):

            l = l + 1

            if int(depth) <= l:
                print
                print 'Depth Reached'
                print
                break

            print
            print '-----------------'
            print ('Analyzing %s of %s: ' %(l, depth)),
            print colored('  %s' %(saved.title), 'yellow')

            if saved.over_18 == False:
                print colored ('    SFW', warn)
                continue

            # define the target subreddit for when we create the directories
            targetSubreddit = saved.subreddit

            savePath = '%s/%s/' % (targetSubreddit, target)

            analyze()

            print

elif process == 'friends':
    print colored ('Downloading Friends List', info)
    print colored ('..Creating new mates.txt', info)
    mates = open('reddit/mates.txt', 'w')

    for friends in r.user.get_friends():

        print friends.name
        mates.write('%s\n' %friends.name)


        ruser = r.get_redditor(friends.name)
        
        for saved in ruser.get_submitted(limit=25):
        
            date_now = datetime.date.today()
            date_created = datetime.date.fromtimestamp(saved.created) # .strftime('%Y-%m-%d')

            date_delta = date_now - date_created

            if date_delta.days > 180:
                print colored ('    Too Old: %s days since last post.' %(date_delta.days), success)
                break

            print '-----------------'
            print colored('  %s' %(saved.title), 'yellow')

            if saved.over_18 == False:
                print colored ('    SFW', warn)
                continue

            # define the target subreddit for when we create the directories
            targetSubreddit = saved.subreddit

            savePath = '%s/%s/' % (targetSubreddit, friends.name)

            analyze()

            print
    mates.close()

elif process == 'album':

    print colored ('Analyzing %s' %(link), info)

    class Stash:
        pass

    saved = Stash()

    url = link.split('/')
    sid = url[6] # short url
    cid = url[8] # comment url

    submission = r.get_submission(submission_id=sid)

    flat_comments = praw.helpers.flatten_tree(submission.comments)
    for comment in flat_comments:
        if comment.id == cid:
            saved.url = re.search("(?P<url>https?://[^\s]+)\"", comment.body_html).group("url")
            savePath = '%s/%s/' %(submission.subreddit, submission.author)
            saved.id = submission.id

    print colored ('Downloading %s to %s' %(saved.url, savePath), info)
    print

    imgurAlbum()

elif process == 'research':
    print colored('Researching %s' %(redditor), info)
    date_now = datetime.date.today()


    #Add to log file
    f = open (prepath + 'researched.txt', 'a')
    f.write('%s, %s\n' %(redditor, date_now))
    f.close()

    ruser = r.get_redditor(redditor)
    url_list = []
    count = 0

    for saved in ruser.get_submitted(limit=int(500)):

        count = count + 1

        print
        print '~---_ %s _---~' %(count)
        print colored('  %s' %(saved.title), 'yellow')

        if saved.over_18 == False:
            print colored ('    SFW', warn)
            continue

        if saved.url in url_list:
            print colored("Duplicate URL: %s" %(saved.url), warn)
        else:
            url_list.append(saved.url)

            # define the target subreddit for when we create the directories
            targetSubreddit = saved.subreddit

            savePath = '%s/%s/' % (targetSubreddit, redditor)

            analyze()

elif process == 'manual':
    print colored('Manual Mode', info)

    url = link[2].split('/')
    sid = url[3] # short url id
    print colored('    Reddit URL: %s' %(sid), info)

    saved = r.get_submission(submission_id=sid)


    print colored('    Title: %s' %saved.title, info)

    print colored('    Link: %s' %saved.url, info)

    savePath = '%s/%s/' %(saved.subreddit, saved.author)

    print colored ('Downloading %s to %s' %(saved.url, savePath), info)
    print
    analyze()

    print


print colored ('> Done <', 'grey', 'on_yellow')
