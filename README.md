
## Happy tube

- fetch videos from search - per category & length & order
- asses from title & description whether they seem happy + add "publishable"
- fetch details (?) (not sure whether entirely necessary now ?)
- [nth] fetch comments & asses whether happy 
- [nth] statistics about channels - maybe we could rely more on known channels ?

### storage
- RequestLog to store
 - request id
 - request time
 - params (flattened)
 - num new results (after deduplication)
 - num happy results
- source data - json, in dirs per month & day, identified by type and ID
- processed data - parquet (?), after dropping duplicates. 

locally vs cloud ... mother duck ? blob ?


## TODO
- parse `thumbnails`, put the middle one into the df
- store stats about the call to claude - how long it took, tokens ...
- experiment with much smarter propmpt
- try varipus models, observe the happiness distribution


## tech ideas
- do it in several async loops with a queue in the middle ?
- structured logging into csvs (per day, week ?), eventually blob or so
 - wrapper ? to reduce repetition ... or DI ?


 parent log
 parent config

 log gets config as argument and stores its fields


## https://www.googleapis.com/youtube/v3/search

according to https://developers.google.com/youtube/v3/docs/search/list

part=snippet




in case i manage to identify channels channelId

maxResults=50

order=rating

q = general query - do we bother ?

regionCode=CZ

safeSearch=strict

topicId - look at the page, should be useful

type=video

videoCategoryId= as per https://developers.google.com/youtube/v3/docs/videoCategories

https://www.googleapis.com/youtube/v3/videoCategories?part=snippet&regionCode=CZ





