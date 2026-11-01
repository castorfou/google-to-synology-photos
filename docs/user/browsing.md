# Browse the NAS Library

## Sign in

The Household signs in with the NAS Account. Nobody needs an account of their own.

- **In a browser:** open DSM at the NAS address, sign in, and open **Synology Photos**.
- **On a phone:** install the **Synology Photos** app, and sign in with the NAS address and the NAS Account.

You can reach the NAS at home, or from outside through a VPN to your home. The tool does not need the NAS to be open to the internet, and we advise against it.

After an import, the NAS works for some hours in the background to make thumbnails. Some photos may look blank until it finishes.

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
