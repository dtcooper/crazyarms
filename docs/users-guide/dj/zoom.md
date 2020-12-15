# Zoom

Here are the instructions to start [Zoom](https://zoom.us/) broadcasting via a room.

## Prerequisites

1. The systems administrator must have enabled Zoom (In the `.env` file, set
   `ZOOM_ENABLED=1`).
2. You must have Zoom installed (<https://zoom.us/>).

!!! warning "Zoom Time Limits"
    If you're _not_ using a paid Zoom account, or your systems administrator has
    not set up a paid account, there are room time limits for group meetings
    held in Zoom rooms. (40 minutes at the time of this writing.) Your show will
    be capped at that length.


## Walkthrough

1. Create and start a Zoom room.
2. Click on the _Meeting Information_ icon, shown below.
    ![Zoom Instructions Screenshot #1](../../img/zoom-instructions-1.png)
1. In the Meeting Information pop-up, copy the link to the Zoom by clicking
   _Copy Link_, show below.
    ![Zoom Instructions Screenshot #2](../../img/zoom-instructions-2.png)
1. Paste the link into the _Room Link_ input, choose a show length, and
    click _Start Zoom Broadcast Now._
1. As soon as the **Broadcast Bot** has entered your Zoom room, your show
    starts, however you must produce make noise for the stream to transition
    to your show. This way, you can set up your show a little bit early. Just
    be quiet until you're ready!

!!! danger
    If a **Broadcast Bot** attendee does not enter your Zoom room roughly
    15 seconds after you click _Start Zoom Broadcast Now_, please contact
    the systems administrator or
    [report a bug with Crazy Arms](https://github.com/dtcooper/carb/issues).
