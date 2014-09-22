#opensubtitles.org
#Subtitles service allowed by www.OpenSubtitles.org
import difflib

OS_API = 'http://plexapp.api.opensubtitles.org/xml-rpc'
OS_LANGUAGE_CODES = 'http://www.opensubtitles.org/addons/export_languages.php'
OS_PLEX_USERAGENT = 'plexapp.com v9.0'
subtitleExt       = ['utf','utf8','utf-8','sub','srt','smi','rt','ssa','aqt','jss','ass','idx']
 
def Start():
  HTTP.CacheTime = CACHE_1DAY
  HTTP.Headers['User-Agent'] = 'plexapp.com v9.0'

@expose
def GetImdbIdFromHash(openSubtitlesHash, lang):
  proxy = XMLRPC.Proxy(OS_API)
  try:
    os_movieInfo = proxy.CheckMovieHash('',[openSubtitlesHash])
  except:
    return None
    
  if os_movieInfo['data'][openSubtitlesHash] != []:
    return MetadataSearchResult(
      id    = "tt" + str(os_movieInfo['data'][openSubtitlesHash]['MovieImdbID']),
      name  = str(os_movieInfo['data'][openSubtitlesHash]['MovieName']),
      year  = int(os_movieInfo['data'][openSubtitlesHash]['MovieYear']),
      lang  = lang,
      score = 90)
  else:
    return None

def opensubtitlesProxy():
  proxy = XMLRPC.Proxy(OS_API)
  username = Prefs["username"]
  password = Prefs["password"]
  if username == None or password == None:
    username = ''
    password = ''
  token = proxy.LogIn(username, password, 'en', OS_PLEX_USERAGENT)['token']
  return (proxy, token)

def fetchSubtitles(proxy, token, part, imdbID=''):
  langList = [Prefs["langPref1"]]
  if Prefs["langPref2"] != 'None' and Prefs["langPref1"] != Prefs["langPref2"]:
    langList.append(Prefs["langPref2"])
  if Prefs["langPref3"] != 'None' and Prefs["langPref1"] != Prefs["langPref3"] and Prefs["langPref2"] != Prefs["langPref3"]:
    langList.append(Prefs["langPref3"])
  for l in langList:
    Log('Looking for match for GUID %s and size %d' % (part.openSubtitleHash, part.size))
    subtitleResponse = proxy.SearchSubtitles(token,[{'sublanguageid':l, 'moviehash':part.openSubtitleHash, 'moviebytesize':str(part.size)}])['data']
    #Log('hash/size search result: ')
    #Log(subtitleResponse)
    if subtitleResponse == False and imdbID != '': #let's try the imdbID, if we have one...
      subtitleResponse = proxy.SearchSubtitles(token,[{'sublanguageid':l, 'imdbid':imdbID}])['data']
      Log('Found nothing via hash, trying search with imdbid: ' + imdbID)
      #Log(subtitleResponse)
    if subtitleResponse != False:
      for st in subtitleResponse: #remove any subtitle formats we don't recognize
        if st['SubFormat'] not in subtitleExt:
          Log('Removing a subtitle of type: ' + st['SubFormat'])
          subtitleResponse.remove(st)
      st = sorted(subtitleResponse, key=lambda k: int(k['SubDownloadsCnt']), reverse=True) #most downloaded subtitle file for current language
      for sub in st:
	Log('Comparing %s and %s' %(sub['SubFileName'], part.file))
	score = difflib.SequenceMatcher(None,sub['SubFileName'], part.file[21:]).ratio()
	lastScore = float(0.0)
	if (score*100) >= 60:
	  if lastScore < score:
	    Log('Chosing sub %s that scored %s' % (sub['SubFileName'],str(score)))
	    st = sub
	    lastScore = score
        else:
	  if score <60:
            st = sorted(subtitleResponse, key=lambda k: int(k['SubDownloadsCnt']), reverse=True)[0]
      if st['SubFormat'] in subtitleExt:
        Log(st)
        subUrl = st['SubDownloadLink']
        subUrlElements = subUrl.rsplit('/',1)
        subFilename = subUrlElements[0]
        subGz = HTTP.Request(subUrl, headers={'Accept-Encoding':'gzip'}).content
        subData = Archive.GzipDecompress(subGz)
        part.subtitles[Locale.Language.Match(st['SubLanguageID'])][subFilename] = Proxy.Media(subData, ext=st['SubFormat'])
    else:
      Log('No subtitles available for language ' + l)

def lcs(word1,word2):
	w1 = set(word1[i:j] for i in range(0,len(word1))
		for j in range (1,len(word1)+1))
	w2 = set(word2[i:j] for i in range(0, len(word2))
		for j in range(1,len(word2)+1))
	common_subs = w1.intersection(w2)
	
	sorted_cmn_subs = sorted([(len(str),str) for str in list(common_subs)])

	return sorted_cmn_subs.pop()[1]

class OpenSubtitlesAgentMovies(Agent.Movies):
  name = 'OpenSubtitles.org'
  languages = [Locale.Language.NoLanguage]
  primary_provider = False
  contributes_to = ['com.plexapp.agents.imdb']
  
  def search(self, results, media, lang):
    Log(media.primary_metadata.id)
    Log(media.primary_metadata.id.split('tt')[1].split('?')[0])
    results.Append(MetadataSearchResult(
      id    = media.primary_metadata.id.split('tt')[1].split('?')[0],
      score = 100
    ))
    
  def update(self, metadata, media, lang):
    (proxy, token) = opensubtitlesProxy()
    for i in media.items:
      for part in i.parts:
        fetchSubtitles(proxy, token, part, metadata.id)

class OpenSubtitlesAgentTV(Agent.TV_Shows):
  name = 'OpenSubtitles.org'
  languages = [Locale.Language.NoLanguage]
  primary_provider = False
  contributes_to = ['com.plexapp.agents.thetvdb']

  def search(self, results, media, lang):
    results.Append(MetadataSearchResult(
      id    = 'null',
      score = 100
    ))

  def update(self, metadata, media, lang):
    (proxy, token) = opensubtitlesProxy()
    for s in media.seasons:
      # just like in the Local Media Agent, if we have a date-based season skip for now.
      if int(s) < 1900:
        for e in media.seasons[s].episodes:
          for i in media.seasons[s].episodes[e].items:
            for part in i.parts:
              fetchSubtitles(proxy, token, part)
