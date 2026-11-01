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
4. On the application permissions step, allow **Synology Photos** and **File Station**. The tool needs File Station to replace changed files.
5. Finish the wizard.

!!! note "Two-factor login"
    You can turn on 2FA for the NAS Account. The tool asks for the code once, then remembers this computer.

## Create the `takeout` folder

This folder keeps every Takeout Export and Album Download.

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
