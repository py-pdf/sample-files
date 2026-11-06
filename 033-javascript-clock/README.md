# A picture that follows the clock, using JavaScript

`javascript-clock.pdf` shows a landscape that changes with the time of the
viewer:

* **Hour**: the sun or the moon on its arc over the sky, the brightness of the
  sky and the ground, a red sky at dawn and dusk, and stars at night.
* **Month**: a tree that is bare with snow in winter, has buds in March,
  blossoms in April, green leaves in summer, and colored and falling leaves in
  autumn.
* **Minute**: a penguin walks across the page once per hour, to the right in
  the first half hour and back in the second one. It changes its step every
  second.
* A digital clock and the name of the month in two text fields.

A document-level JavaScript runs once per second. Every picture is the
appearance of a read-only push button; 24 skies, 12 trees and 120 penguins
(60 minutes, two steps), of which the script shows one each with the `display`
property of the field and hides the others. PDF.js only does that for push
buttons that have a JavaScript action, so every picture has one that does
nothing.

Without JavaScript, a viewer shows noon in June with the penguin in the middle,
and the text fields show `--:--:--` and `needs JavaScript`.

Tested in Firefox 157 (PDF.js). Programs that only render the page, like
MuPDF, Poppler or pdfium without JavaScript, show the default picture.

The file is useful to test

* document-level JavaScript (the `/JavaScript` name tree);
* hidden annotations (annotation flag 2), which must not be drawn;
* push buttons and text fields with appearance streams;
* appearance streams whose bounding box is not at the origin, and form
  XObjects used by several appearance streams.

## Create the file

```
python create_javascript_clock.py
```

The script needs no package besides Python 3.9 or later, and creates the same
file every time.

## License

The files are released under the CC-BY-SA-4.0 license.
