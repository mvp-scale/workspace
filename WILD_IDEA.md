Jev
0:00
At this point, I'm sure you've heard of
0:01
Jev. It's a new model. It is super fast
0:04
and you can use it to do classification.
0:06
They refer to it as a system one model
0:08
implying that it's meant for system one
0:10
thinking, which implies that it could be
0:12
used for classification kinds of tasks,
0:14
but I've not really seen a lot of videos
0:15
on YouTube where someone is actually
0:17
trying to do a proper benchmark to
0:18
compare it against maybe some classic
0:20
techniques. Now, for starters, just to
When not to Jev
0:22
be clear, Jev isn't perfect. you're
0:25
still sending data to a third party and
0:27
I've tried to use it this morning and
0:29
the system was overloaded and down. You
0:32
also can't fine-tune Jev. So, if you're
0:34
trying to give it some text, maybe some
0:36
non-English internet slang, then the
0:38
results can be pretty mixed, too. And
0:40
when that's the case, there's no
0:41
fine-tuning you can do to change that.
0:43
All this to say that there are good
0:45
reasons that you might still want to
0:46
roll out your own classifiers, but at
0:48
the same time, you can't deny the appeal
0:51
of a system like Jev. It's fast and the
0:53
API is so cheap that it makes pennies
0:56
look expensive. And it's looking like
0:57
we're hitting this point where you may
0:59
not need a big data set with labels in
1:02
order to make a sensible classification
1:04
system work or at least to make a
1:05
version one work. So I'm going to
1:08
actually try to benchmark this. And to
1:10
do that, I'm going to compare Jeff to
1:11
some old school machine learning tricks
1:13
that I remember. And as we'll see, Jeff
1:15
can do classification, but the kind of
1:17
model that it represents, it's really
1:19
best not to think of it as a
1:20
classification model. We're going to see
1:22
in a moment why. It's going to take me
Ready Set Fit
1:24
some time to explain what I mean by
1:25
this. So, what I'll do first is just
1:27
explain this one machine learning
1:28
technique that I think is going to be
1:30
the fairest comparison to Jev. Now,
1:34
let's imagine that we have some training
1:35
data, but not a whole lot. Let's say
1:37
it's something like this. In total over
1:39
here, we have about eight examples. Four
1:42
items that are positive, four that are
1:43
negative. And we would like to make a
1:45
classifier as good as possible using
1:48
only these eight data points.
1:52
Well, what you could do is you could
1:53
just pass it through a neural network
1:54
that can do an embedding of sorts and
1:56
then if the embedding is good, then
1:58
maybe you could build a classifier. You
1:59
could use a logistic regression to maybe
2:01
split up the data set, maybe something
2:03
along this axis. But you're going to
2:05
have to be quite lucky. After all,
2:07
there's not a whole lot of data points
2:08
if you think about it. But most of all,
2:11
this embedding step over here, it's
2:14
probably trained on a very generic task,
2:16
and we're interested in actually having
2:18
a embedding that's really good for this
2:20
specific task. So, one way of thinking
2:22
about this is that maybe we want to
2:23
infer some knowledge of our data to make
2:26
the embedding step work as well as
2:27
possible over here, especially given the
2:30
fact that we only have a few data points
2:31
to begin with.
2:35
So, here's a trick that you could do,
2:37
and you might recognize this as the set
2:40
fit trick. What you can do is you can
2:42
turn eight data points into many by
2:45
looking at pairs that are in agreement.
2:50
You can generate a bunch of these. And
2:52
once you have a few pairs that agree,
2:54
well, you can also look at pairs that
2:56
disagree. [music]
2:59
In some sense, we are now changing the
3:00
classifier. When two items disagree, we
3:03
are giving it the label zero. And when
3:06
two items are in agreement, we give it
3:08
the label one. So, we're no longer
3:10
really talking about this positive or
3:12
this negative label. No, we are now
3:14
talking about similarity instead.
3:16
[music] And depending on the data set,
3:18
you can generate a whole lot of these
3:19
pairs, even if you only have a few data
3:22
points that you're starting out with.
3:27
This is the first step. You take your
3:28
small data set of labels and you try to
3:31
turn that into a larger data set of
3:32
pairs.
3:37
Then what you could do is you could pass
3:40
every pair through a embedding model.
3:42
And it's really important that the
3:44
embedding model is the exact same. This
3:46
text is going to go through this model
3:48
that's going to generate this embedding.
3:51
And when you pass it a different text,
3:52
it is going to give you a different
3:54
embedding. But it's really important to
3:56
understand that these two embedding
3:58
models are in fact the same one. And
4:00
then from here what you can do is you
4:02
can calculate the cosine similarity.
4:04
This is a number derived of the angle
4:05
between the two vectors.
4:08
And the interesting thing about it is
4:10
that we can turn this into a metric that
4:12
we can optimize. After all, we could
4:14
calculate a loss. This cosine similarity
4:17
number over here, that's going to be
4:18
very close to one if these two vectors
4:21
[music] are in fact similar. And that
4:23
label y that we started with, well that
4:25
indicates if these two examples belong
4:28
to the same class. And in short, we are
4:30
now using cosine similarity compared to
4:32
the similarity label. We're squaring
4:35
that. So we get a mean square distance
4:37
over here.
4:39
If the cosine similarity was higher, the
4:42
loss would of course be lower and vice
4:44
versa.
4:46
Now, of course, the big picture idea
4:47
here is that we do get this loss over
4:50
here, and we can use a gradient update
4:53
signal to travel and to actually update.
4:56
We're going to propagate all the way
4:58
through to this embedding model over
5:01
here. And the whole point of this is to
5:03
actually end up with a embedding model
5:05
that's going to be better for the task
5:06
that we are interested in doing. If this
5:09
embedding model is better at caring
5:11
about this similarity, then it might
5:13
also help us in the step after when we
5:15
want to make a classification.
5:19
So we have our embedded space and then
5:21
we start training.
5:24
You're going to notice that we have a
5:25
connection between all of these points.
5:27
Red lines indicate that we want to add
5:28
more distance. Green lines indicate that
5:31
we want to pull things together more.
5:32
And as we start training, you're going
5:34
to notice clusters start to form and
5:37
they're going to be easy to separate.
5:42
And then after a few epochs, we will
5:44
have our fine-tuned encoder that's going
5:46
to give us a slightly different
5:47
embedding than what we would have
5:49
before. But the hope is that by now, if
5:52
we were to do any machine learning
5:53
model, it'd be super easy to make the
5:56
two [music] classes split up.
6:01
And of course for any new data points
6:03
that come in, they would also be mapped
6:05
and moved along.
6:08
So even though we only start with eight
6:11
examples, we might still generate a
6:13
mapping that in general would behoove
6:15
the classification that we want to do.
Results
6:17
So that is set fit [music] and it's one
6:21
of the models that I'm using in my
6:22
benchmark and you can see that I'm
6:23
running a few over here. So there's a
6:25
[music] couple of these classification
6:27
data sets. I've got AG News. I've got a
6:29
few down below over here. But the main
6:31
thing I want to show just for now is the
6:33
models that I'm using. I'm doing a basic
6:35
scikitlearn pipeline over here. I'm
6:38
using normal sentence transformers as an
6:40
embedding technique with logistic
6:41
regression. That does a bunch better as
6:43
you can see over here. Then I'm going to
6:46
use better embedding models like the
6:47
Quen 3 embedding model over here with
6:49
logistic regression. We get better and
6:51
better and better. But then eventually
6:53
we get to the performance of set fit
6:55
over here. that's going to use the cheap
6:58
embedding model, the one from almost 10
7:00
years ago. And what you're going to
7:01
notice is that we do way better than
7:04
anything that we saw before. So set fit
7:07
as a technique in general, it does work
7:09
pretty well. And the thing that's really
7:11
cool about it is that we are only using
7:13
uh eight training examples per class. So
7:15
for all of these different data sets
7:17
that I have, only eight examples of each
7:19
class is enough for set fit to do its
7:21
thing, at least on these benchmark data
7:24
sets. But then I figured that's a good
7:26
solid benchmark. Not a whole lot of
7:27
effort was needed to generate the
7:29
training data. So that feels somewhat
7:31
comparable to Jev. Then I compare it to
7:33
Jeff down below over here. And you can
7:35
see click boom. That's a good 9%
7:39
increase. So the state-of-the-art method
7:41
from 5 to 7 years ago for few shot
7:43
learning that is being outperformed by a
7:46
mere API call that is costing me a penny
7:49
and a half on this validation data set.
7:52
And that's something that I see over
7:54
here in the AG News data set, but I
7:56
could show you some more. For the TRE
7:57
data set, I also see Jev perform way
7:59
better than anything that came before
8:01
it. Also around the 90% mark. Uh, one
8:04
thing that does matter in Jev, you can
8:06
actually describe the labels. And when
8:08
you do that, you do get a performance
8:10
boost. That's what you see over here.
8:12
So, if you're able to add a description
8:13
of the label, that definitely does make
8:15
everything better. But also on 20 news
8:17
groups, Jeff is just way better. And at
8:19
Clink 150, it is also way better. And
8:22
this is super interesting because clink
8:24
150 is a data set where set fit just
8:26
completely fails. The reason why it
8:29
fails is because it has 150 classes. And
8:32
if you want to make all these different
8:33
pairs between all these different
8:35
classes, then suddenly for something
8:37
like setfit, your training procedure is
8:39
actually going to blow up a bit. It
8:41
might take a long time to train. Jev on
8:43
the other hand has no problem with it
8:45
whatsoever. But it does feel safe to say
8:47
in this particular case that if you were
8:48
to use a embedding model with a logistic
8:50
regression that you'd be pretty close to
8:52
this Jeff model as well. And these are
8:55
all models that you can run locally. Now
Important!
8:57
one thing that's really important to
8:58
highlight here is that even if you're
9:00
not interested in running Jeff in
9:02
production as your production model,
9:04
just this is already super good news
9:07
because it means that we have a model
9:08
that's going to be good for us to find
9:10
bad labels. So one thing that you can
9:13
always do is you can point Jeff to a
9:15
data set and then you can just say look
9:18
give me all the examples where you
9:20
disagree with the actual label. And in
9:22
my experience it turns out especially if
9:24
you go for the very confident
9:26
predictions that Jeff turns out to be
9:28
right pretty often. So this one example
9:30
the label is sci and technology. Jeff
9:33
says it's about business. And when you
9:35
read the text you know venture capital
9:37
summer vacation it's a drop in
9:39
investments. I understand that when it's
9:41
about VCs, it might be about tech, but
9:43
in this case, it's definitely about
9:44
business, too. So, if Jeff is
9:46
complaining that there's a bad label
9:47
here, I would uh definitely sympathize.
9:49
So, that's also a really good use case
Qwen
9:51
of these models, right? So, Jev is
9:53
pretty good and it's available. It's out
9:55
there. And in general, that could be
9:57
very good news. But I can also hear some
9:59
of you think, ah, that's actually a
10:01
bummer because I don't want to send my
10:02
data to a third party in order to
10:04
benefit from all of this. And here I do
10:06
want to give you some reasons for
10:08
optimism too because if I read what Jeff
10:10
is all about then it's like using a
10:13
large language model but not training it
10:15
to give you large quantities of text but
10:17
instead to give you just a minimal
10:19
signal at the end. That is also why in
10:21
the uh pricing of Jev you only pay for
10:23
the input tokens. And that suggests to
10:25
me that if you want to do something
10:26
really really similar well you could
10:29
also just take a quen model. I found
10:31
this open source project called decider.
10:33
And what you can literally do there is
10:34
pass it a model that's I think on
10:36
hugging face. Uh I'm using decider 2B
10:39
over here, but I'm also passing some of
10:40
these uh basic Quen models. And what
10:42
this decider model is then able to do is
10:44
you can give it some text with some
10:45
instructions like a small prompt that
10:47
says, hey, this is the text and here's
10:49
the classification that I need. And what
10:51
it's then going to do is it's actually
10:52
just going to pretend to do the normal
10:54
quen run, but then we're going to look
10:55
at the output tokens and see which match
10:58
the labels that we might expect the
10:59
most. And then we're going to see if
11:00
that can perform like our classifier as
11:02
well. And it turns out when you do this,
Outperform Jev
11:04
and again I've been trying this out on a
11:06
whole bunch of models, when you add
11:07
those Quinn models, then we actually see
11:10
that the base decider model and the Quen
11:12
model depends a bit on the data set, but
11:14
that can actually outperform Jev. Now,
11:17
it might be a bit slower depending on
11:18
the inference that you have available to
11:20
you, but in general, I have found that
11:22
that decider package together with Quinn
11:24
is competitive with Jev on all of these
11:27
base classification tasks. Not always.
11:29
Sometimes it's a little bit worse, but
11:31
sometimes it's also a little bit better.
11:33
So, if you're keen to run these models
11:35
yourself locally, well, even if you
11:36
don't use the classic machine learning
11:38
techniques, you can still get there by
11:40
using these larger language models this
Not a classifier
11:43
way. And on that front, there's this one
11:45
final benchmark that I think is
11:46
important to show you, and that's
11:47
related to this uh Google bool question
11:51
data set. It's an old data set. It comes
11:53
from 2019, but it's a data set where
11:56
there's a passage like this one that's
11:58
about phantom pain sensations. There's a
12:00
couple of sentences, maybe a small
12:01
paragraph, and then there is a question
12:03
about the paragraph. Is the pain
12:05
experienced in a missing body part or
12:07
paralyzed area. And then that question
12:10
is either leading to a true or a false
12:12
answer. And the whole point of this data
12:14
set is you could argue it's kind of like
12:16
a classifier because text goes in, you
12:19
could pass the passage along with the
12:20
question and that could be seen as a
12:22
binary classification of sorts, but
12:24
historically that has never really
12:26
worked well, at least in a classical
12:28
machine learning sense. And the reason,
12:30
frankly, is because this is barely a
12:32
classification problem. It's almost a
12:34
retrieval problem more than anything
12:36
else. So sure you might be able to do
12:38
something clever where you embed the
12:39
passage and then separately you embed
12:41
the question and then you're going to
12:43
fine-tune to matching those two kind of
12:46
like what you do in set fit but then you
12:48
are building a very specialized system
12:50
and you're not really a classical oath
12:52
we only have to embed one thing one
12:54
class we're kind of outside of that
12:56
domain but if you still want to do
12:57
something like this Jeff will work quite
Some numbers
13:00
well so I tried it on this one data set
13:02
I've taken 500 of these questions and we
13:05
get about a 93% accuracy. What I figured
13:08
I would do is again use that Quen trick.
13:10
And you're going to notice that when I
13:12
do that, you know, I tried the 0.8B all
13:14
the way up to 9B. The accuracy for 9B
13:17
kind of gets close, but it definitely
13:19
feels like you're typically always lower
13:20
than Jev. But here's kind of the
13:22
beautiful thing. Even if you have a data
13:24
set where you have examples, but no
13:25
labels, you can actually point Jeff to
13:28
that data set to generate those labels
13:30
and then fine-tune your own system after
13:32
the fact. So here's my training run. You
13:35
can see the loss go down. I'm training
13:37
for 0.8, 2B, and 4B over here. And what
13:40
you can also see is that where before we
13:43
had 73%
13:45
after fine-tuning, we have 87% accuracy.
13:49
Where before we had 67, for the 2B1, we
13:52
now have 88. And for 4B, we had 84% and
13:56
now we have 91. So, you know, all in
13:58
all, the thing that Jev represents to me
14:00
that's pretty exciting is that we have
14:02
this new Lego brick. And maybe that's
14:03
also the way to think about it. Now,
Venn
14:05
with all that said, there's this one
14:06
final comment I think that's important
14:08
to take serious. Historically, we've
14:09
always had classification models. And
14:12
some of the commentary that I see
14:13
online, especially from the like data
14:15
science perspective, is that people are
14:16
saying, look, we now have this thing
14:18
called Jev, and this is a new kind of
14:20
model. And look, it can do
14:21
classification. But maybe the way to
14:23
think about Jev is to say, well, yeah,
14:26
there's a vin diagram, but boy, does it
14:29
overlap. that system one level thinking
14:32
that it's trying to do. Yes, it can
14:34
perform classification and yes, it's
14:35
super useful because there's tons of
14:37
applications for it, but you also get
14:39
just that little bit of quick reasoning
14:41
attached and that goes beyond what you
14:43
would normally associate with a
14:45
classification task. There are lots of
14:47
use cases where if you had a good
14:49
embedding model, you could apply the set
14:50
ffit thing and you know that's something
14:52
that Jeff and maybe there's a chunk over
14:54
here that Jeff doesn't you know where
14:56
you don't want to send something to a
14:57
third party API or something but there
14:59
are just so many of these situations
15:01
where here is text here's a summary is
15:04
this a good summary of the text yes no
15:06
where you also need that little bit of
15:08
quote unquote reasoning and if you look
15:10
at their messaging this is also the
15:12
thing that they're trying to get across
15:14
they're calling this a system one model
15:16
and they're not calling this a machine
15:17
learning model because that's not the
15:19
way to think about this. Now, what does
15:21
this mean for you? I mean, it still
15:23
might mean that you want to use the good
15:24
old normal classification models for
15:26
yourself because there's lots of
15:27
benefits to just hosting the thing on
15:28
your own side. And depending on what
15:30
you're doing, you know, it could fair
15:31
well be that you're in this part of the
15:33
van diagram. If for whatever reason your
15:36
Jeff model is not doing very well, you
15:37
might be able to calibrate it in
15:39
hindsight, but you're definitely not
15:40
going to be able to fine-tune it because
15:41
it's hosted somewhere else. For moments
15:43
like that though, I do recommend that
15:45
maybe you look away from Jev and to
15:47
maybe consider system one models in
15:49
general, which you could theoretically
15:51
also fine-tune from a very small LM
15:53
model. And if that's something you're
15:55
interested in doing, all the notebooks
15:56
that I showed you here today are hosted
15:58
on Moab. We give you a free GPU to play
16:01
with. So if you want to experiment and
16:02
maybe do your own little fine tune, you
16:04
can totally do that. Links are in the
16:06
show notes. Thanks for listening.

