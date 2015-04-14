------------------------------

# Overview

SCIpher is a program that can hide text messages within seemingly
innocuous scientific conference advertisements. It is based on the
context-free grammar used in
[SCIgen](http://pdos.csail.mit.edu/scigen), but instead of randomly
piecing together sentences, it uses your input message to control the
text it generates. Then, given SCIpher output, it can recover the
original message by reverse-engineering the choices made at
encoding-time.

One useful purpose for such a program is to communicate secret
messages that don't look like secret messages. Encrypted emails, for
example, might signal to snoopers that you are an interesting person
who bears investigation. However, in our experience when you send out
a Call for Papers (CFP) announcement, it's very unlikely that anyone
will read it.

In addition, you can use these context-free CFPs to solicit
submissions to your very own academic conference. If
[WMSCI](http://en.wikipedia.org/wiki/World_Multiconference_on_Systemics,_Cybernetics_and_Informatics)
could do it, why not you?

# A note on security

**Encoding is not the same as encryption.** If you encode a plaintext
message, anyone with access to SCIpher can recover your message given
the encoding.  If what you are sending is truly secret, please encrypt
is first using PGP or some other method.  That way, your message is
safe, and at the same time, anyone on the lookout for encrypted
messages may not notice it.

# Requirements

* Python 2.7
* [NLTK](http://www.nltk.org/install.html)
  * You don't need to install Numpy, it isn't required for SCIpher.
* [ZeroMQ for Python](http://zeromq.org/bindings:python)

# Usage

There are two ways to run SCIpher.

## Script mode

The simplest way is using the encoder/decoder scripts directly:

    echo "This is a secret" | ./encode.py

This will print your encoded message on stdout (and print the random
seed on stderr -- see below).  Let's say you saved the stdout in a
file called 'msg.txt'.  Decode it simply with:

    cat msg.txt | ./decode.py

## Daemon mode

The above method is a little slow, because it has to load and parse
the full grammar each time the script runs.  If you will be encoding
or decoding many messages, it might make sense to run it as a daemon:

    ./scipherd.py --socket /tmp/scipherd.sock --workers 2

This starts a SCIpher daemon (not a real, backgrounded daemon though,
just a regular process) listening on a Unix domain socket, with two
worker threads.  You can encode and decode messages almost just as
before, but faster:

    echo "This is a secret" | ./encode.py --socket /tmp/scipherd.sock | ./decode.py --socket /tmp/scipherd.sock

# Restrictions

* Input messages must be 1 MB or less.  Bigger messages must be split
  across multiple CFPs.
* Input characters must have a Unicode code point of less than 256.
  Unfortunately this leaves out a good number of non-english special
  characters.  We hope to fix this in the future.

# Options

## Files

encode.py and decode.py read from stdin and write to stdout by
default, but they can both take `--infile` and `--outfile` parameters
to use files instead.

## Deterministic encoding

As explained below, encoding the same message multiple times results
in different encodings.  If you want to regenerate the same message
deterministically ever time (perhaps for debugging), you can pass in
`--seed`.  During each encoding, if `--seed` is not given, the program
picks one at random and prints it to stderr in case you need to
generate the same encoding again.

## Website

You might want to direct your CFP receivers to a particular website,
just like a real CFP.  In that case, pass in `--website` and it will
be done.

# How it works

An unambiguous context-free grammar is simply a decision tree.  At the
top of the tree is a rule defining all the possible ways a document
conforming to that grammar can be written.  For example, let's say you
want to write a grammar for essays that would be between 3 and 5
paragraphs long.  You might have starting rules that looks like this:

    START -> PARAGRAPH PARAGRAPH PARAGRAPH
    START -> PARAGRAPH PARAGRAPH PARAGRAPH PARAGRAPH
    START -> PARAGRAPH PARAGRAPH PARAGRAPH PARAGRAPH PARAGRAPH

Then, if you were given an essay that conforms to the grammar, you
could _parse_ it and figure out which of the above three rules was
used to make that essay.

The insight here (which is
[not original](http://pdos.csail.mit.edu/scigen/scipher.html#relwork)
to SCIpher) is that you can communicate information in your choice of
rule.  Let's say you wanted to tell your friend to meet you at 2
o'clock; you could send her an essay that has 4 paragraphs, and then
she can parse it, see that it matches the 2nd rule, and understand
that you are saying "2".

This is the essence for how SCIpher works.  It uses an unambiguous
context free grammar (cfp\_header.cfg and cfp\_body.cfg), consisting
of a many rules like the above that describe the paragraphs, lists,
sentences and words that together will form a CFP.  When you input
your secret message, the encoder breaks it up into a stream of 1s and
0s by converting each character in the message into its Unicode code
point (some number less than 256, represented in 8 bits of binary).
Then the encoder starts at the beginning of the grammar, and reads
enough bits from the stream to unambiguously choose one of the
starting rules.  Then it repeats the process using all the subrules
referenced in that rule, and so on, until all the bits have been used.

The decoder then parses the message to recover the decision tree used
to generate the message, and recovers the binary representation of
your message by figuring out which choice was used at each decision
point, converting that into a number (like the "2" example above), and
concatenating all those numbers together.  Then each 8-bit sequence of
bits is treated like a Unicode code point and changed back into a
character.  Simple!

## Issues

Or maybe not so simple.  Implementing the above scheme naively leads
to some problems:

* _Each particular input message would generate the same encoding:_
  This isn't a huge deal, but one of the goals of this project was to
  make funny CFPs.  If someone generated one they didn't like, we'd
  like them to be able to try again with the same secret and get a
  different one.  Also, if different people use the same input
  message, and send around the same encoding, it might make it easier
  to recognize and decode.
* _The grammar must never change:_ Both the sender and receiver
  need to have the exact same grammar.  That meant once we unleashed
  this program, we would never be able to change the grammar, because
  messages encoded by the old version would be unreadable.
* _The recipient can't tell when the message ends:_ The encoder might
  run out of bits before it generates a complete message that conforms
  to the grammar.  After that, what does it use to make choices?  If
  it just picks randomly, how does the decoder know not to interpret
  those random choices as characters in the input message?
* _Either the grammar or the encodings would be very, very big:_ It
  turns out that this isn't a terribly efficient way of transmitting
  information.  In the above example, you had to generate up to 5
  paragraphs of text just to send a secret one-digit number to your
  friend!  However, if you had 2^1024 possible starting rules, you
  could send 1024 bits of information with that first decision.  Thus,
  either your grammar is large, or your encoded messages must be big.

## Header

We solve the first three of these issues by including a _header_ with
every message.  This is the first line of the encoding (representing
the "subject" line of the CFP).  We use this header to convey some
metadata about the message:

1. A randomly-generated number that changes each time the same secret
   is encoded.
2. The version of grammar that was used to generate the encoding.
3. The length of the message

It would be easy enough to just prepend this information to the input
secret and be done with it.  However, remember that one of our goals
here is to make sure the grammar can freely change, and if the part of
the grammar that was used to encode this metadata changed in a future
version, it would make it impossible to recover the metadata.

So, we instead pre-generated a list of possible conference names that
isn't allowed to change (cfp\_conf\_names.txt).  A particular
conference's line number in the file corresponds to the numeric
representation of the metadata for the encoding.  There are nearly 4
million different conference names, which implies that all line
numbers will have 21 bits.  Here is how the encoder picks which
21 bits to use, in order to pick a conference name:

* The random number, called a _mask_, between 0 and 255 is chosen by
  the encoder.  This is the first 8 bits.
* Each release of SCIpher with a different grammar will have a version
  number associated with it, between 0 and 255.  The version number
  for the current grammar, XOR'd with the random mask, is the second 8
  bits.
* The final 5 bits are the least significant 5 bits of the length of
  the input secret.

We restrict input secrets to 1 MB in length, and so the length only
has 15 other bits.  Those bits (XOR'd with the mask) are used to pick
the rest of the words in the header, according to the grammar in
cfp_header.cfg.  The mask is also XOR'd with all 8-bit sequences in
the input secret.

The decoder can then pick the conference name out of the subject line,
look it up in the list of conference names to get its line number, and
from there figure out the mask, the version number, and part of the
length.  Then it can use the right grammar and the rest of the subject
line to get the rest of the length.

Once it has the length, the decoder knows exactly when it has
recovered enough bits from the encoding, and can ignore everything
else.

## Lists

The final issue above -- the size tradeoff between the grammar and the
encoding -- requires a different tactic.  Coming up with the rules for
the grammar is very time-consuming, and it's just not practical to
write an extremely large grammar by hand.  Instead, we took advantage
of one of the ridiculous aspects of CFPs -- long, repetitive lists.
In real CFPs, there are often lists of program committee members,
topics, past conference locations, etc.  We figured that we could use
these lists to not only encode many bits from the input secret, but
also to make the encodings funnier by having ridiculously long lists
in some cases.  So, we came up with a number of different lists that
can be lengthened indefinitely, and tried to pack them with rules that
used a lot of bits (names and locations chosen from very large lists,
for example).  The lists are made up of a recursive rules, plus one
final non-recursive rule that will end the list whenever it's used.

The trick is deciding when to end a list.  We don't just want the bits
of the input secret to randomly happen upon the non-recursive,
list-ending rule -- this would lead to wildly varying list sizes, and
make the CFP look kind of weird.  (E.g., you could have a list with
thousands of PC members, and then a list with just two conference
topics.)  It would be nice to keep the lists somewhat balanced -- in
our opinion, this is both more realistic and funnier, since it is less
distracting.

So, for each list, the encoder and decoder agree on a _weight_ for
that list, which is essentially the percentage of the total input
secret length that the encoder will use when generating the list.
Once it uses that many bits, it will pick the non-recursive rule and
move on.  With one notable exception: the final list must keep going
until it's used the entire message, otherwise you run the risk of the
grammar ending before you have finished encoding the message.

Since the decoder has the same weights, it can figure out exactly
which choices within a list are part of the input secret, and which
are not.

## Substitutions

You might note that the conference name itself can appear in the CFP.
How can that work, if the body is generated according to the (masked)
bits of the input text, and must follow such a rigid structure?  Well,
basically we cheat: the grammar definition uses a special rule name,
CFP\_CONF\_NAME, that does not resolve to any rules.  Then, after the
encoding is done, there is a second pass over the output to substitute
the conference name from the header everywhere that rule appears.  The
decoder does the reverse substitution before it does a full parsing on
the encoding.

We use the same trick for dates.  We wanted the dates in the CFP to be
in the near future, so the CFP would look more realistic.  So the
grammar itself generates a special rule where the dates should be, and
then the encoder fills those in after the fact, making sure to pick
nearby, monotonically-increasing dates for each subsequent
substitution.

# Making changes to the grammar

The grammar should follow these guidelines:

* It must be unambiguous -- there can never be multiple ways to parse
  a particular encoding.
  * This includes a rule having duplicate productions.
  * `check_grammar.py` and `test.sh` are useful ways to help ensure your
grammar is unambiguous and complete.
* For each rule, it is most efficient to have 2^n+1 productions, where
  n is an integer that is greater or equal to 1.  For example, if you
  have 22 productions for a given rule, 5 of them are wasted
  (22-(2^4+1)) because they won't be used to encode the bits of the
  input secret.
  * The extra (+1) production is used to indicate the end of a list,
    and is only needed for historical reasons.  We can probably do
    without it now and just have 2^n productions for every rule, but
    that will be future work.
