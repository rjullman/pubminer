pubminer
========

Publication data miner.  Currently supports only conferences found in the DBLP bibliography.

### Usage

Use the documentation included in the python script by running

``` python miner.py -h ```

### Output

The publication data is output as JSON populated with whatever fields are found with each mined publication.  Usually a publication contains at least a title and author entry.  See included ```popl-sample.dat``` for sample output.

### Examples

Mine Principles of Programming Languages (POPL) conference publications:

``` python miner.py popl ```

Mine POPL publications without citation data, limiting to the last 10 conferences, and put the output in ```popl10.dat```:

``` python miner.py popl -nc -l 10 -f popl10.dat ```
