# Prepare the NAS

Do these steps once, in DSM, signed in as an administrator.

## Turn on user homes

Each account's private photos live in its home folder, so homes must be on.

1. Open **Control Panel > User & Group > Advanced**.
2. Under **User Home**, tick **Enable user home service**.
3. Click **Apply**.

This creates the `homes` shared folder.

## Install Synology Photos

Open **Package Center**, find **Synology Photos**, and install it.

## Create the NAS Account

The whole Household shares this one account. The tool writes with it, and the Household browses with it. Do not use an administrator account.

1. Open **Control Panel > User & Group > User**, and click **Create**.
2. Choose a name, such as `photos`, and a strong password.
3. Leave the account in the `users` group only.
4. On the application permissions step, allow **Synology Photos**, **File Station** and **SMB**. The tool needs File Station to replace changed files, and your computer needs SMB to reach the `takeout` folder.
5. Finish the wizard.

## Turn on 2FA for the NAS Account (optional)

The 2FA of an account is set up while signed in with that account, and the NAS Account cannot open DSM. So you make DSM ask for it, then set it up from Synology Photos.

1. Open **Control Panel > Security > Account**.
2. Under **2-Factor Authentication**, tick **Enforce 2-factor authentication for the following users**, and choose the NAS Account.
3. In a private browser window, open `https://nas:5001/?launchApp=SYNO.Foto.AppInstance`, and sign in with the NAS Account. Use its user name, not its email address.
4. Follow the wizard: scan the QR code with an authenticator app, and type the code it shows.
5. Keep the backup codes that DSM shows.

Until step 4 is done, the tool cannot log in: it stops with error 406.

The whole Household shares the NAS Account, so each new phone or computer that opens Synology Photos asks for a code. To share the codes, scan the QR code with two phones at step 4.

The tool asks for the code once, then remembers this computer.

## Create the `takeout` folder (as a shared folder)

This folder keeps every Takeout Export, each in its own dated folder, and the `album-downloads` folder. An Album Download is the ZIP of one shared Album, which brings back the photos other people added to it. You need them only after the first import: see [Album Downloads](album-downloads.md).

1. Open **Control Panel > Shared Folder**, and click **Create**.
2. Name it `takeout`.
3. On the permissions step, give the NAS Account **Read/Write**.

The tool reads the ZIPs from this folder, and writes its report there.

## Turn on the `homes` Recycle Bin

We advise this. A photo deleted by mistake on the NAS goes to the Recycle Bin, so you can get it back.

1. Open **Control Panel > Shared Folder**.
2. Select `homes`, and click **Edit**.
3. Tick **Enable Recycle Bin**.
4. Leave **Restrict access to administrators only** unticked, so that the NAS Account can see the bin.
5. Click **Save**.

To get a file back, sign in with the NAS Account, open **File Station**, go to the `#recycle` folder of your home, and move the file back to its folder.

Next: [install the tool](install.md).
