# Browse the NAS Library

## Sign in

The Household signs in with the NAS Account. Nobody needs an account of their own.

- **In a browser:** open DSM at the NAS address, sign in, and open **Synology Photos**.
- **On a phone:** install the **Synology Photos** app, and sign in with the NAS address and the NAS Account.

You can reach the NAS at home, or from outside through a VPN to your home. The tool does not need the NAS to be open to the internet, and we advise against it.

After an import, the NAS works for some hours in the background to make thumbnails. Some photos may look blank until it finishes.

### Previews the NAS cannot make

Some items keep a grey icon instead of a thumbnail, such as a clapperboard with a `?` for a video. The NAS does not make previews for some formats, such as HEIC photos and HEVC videos. Synology Photos then shows "Enable Synology Image Assistant to display more formats".

Synology Image Assistant makes these previews on your computer instead. It has two parts, a browser extension and a desktop app, and both must run while you browse. It needs Windows 11 22H2 or later (not on Arm), or a Mac.

1. In Synology Photos, click **View details** in that message.
2. Next to **Synology Image Assistant Extension**, click **Install**, and add the extension to your browser.
3. Next to **Synology Image Assistant for desktop**, click **Install**, then install and launch the app.
4. Click **Finish**, and browse the photos: the previews are made as you go.

See Synology's [Synology Image Assistant Quick Start Guide](https://kb.synology.com/en-global/DSM/tutorial/Quick_Start_Synology_Image_Assistant).

## What you see

- **Albums** holds every Album, with its Google Photos title.
- The photo timeline shows each photo at its real date.
- The photos are stored in the folder `Google Photos`, with one folder per year.

Open a photo and show its information panel to read its Photo Description:

```text
The Christmas tree

Anna, 2016-12-25: So beautiful!
Paul, 2016-12-26: Merry Christmas
❤️ Anna, Paul
```

- First comes the Caption, then the Comments with their author and date, then a line with the Likes.
- A photo in several Albums shows the Comments of each one. When more than one Album has some, the Album title comes before them.
- The **oldest photo of an Album** starts with the **Album text**: the description of the Album, its Comments and Likes, and the Comments that match no photo.

## Your own Albums

You can make your own Albums on the NAS with your own photos, from outside the `Google Photos` folder. The tool leaves an Album alone when it holds at least one photo from outside that folder.

!!! warning "Do not make Albums only from NAS Library photos"
    The tool cannot tell such an Album from one of its own. At the next Refresh, it may rename that Album and add photos to it. To keep a hand-made Album safe, add at least one photo from outside `Google Photos`.

Next: [run a Refresh](refresh.md).
