# Testing FYI - Group Folder Recommendations

## Steps to Test:

1. **Start the frontend** (if not running):
   ```bash
   npm run dev
   ```

2. **Open the app** in your browser:
   - Navigate to http://localhost:3000

3. **Open Browser Console** (F12 or right-click → Inspect → Console)

4. **Navigate to "New Mail > Other"**

5. **Check the console logs** for:
   ```
   Category distribution: {7: 2, 8: 15, ...}
   Found 2 FYI - Group emails (category 7) without recommendations
   Fetching recommendation for email 37...
   Response status for email 37: 200
   Got recommendation for email 37: {recommended_folder: "Orders", is_new_folder: true, ...}
   ```

6. **Look at the FYI - Group email rows** (category 7):
   - You should see a purple folder icon 📁 with the folder name
   - If it's a new folder, you'll see a "NEW" badge
   - Example: `📁 Orders NEW`

7. **Expand a FYI - Group email** to see the full folder recommendation field

## If it's not working:

Check the console for:
- Any error messages
- The "Category distribution" to confirm you have category 7 emails
- Network tab → XHR to see if the `/api/folders/recommend-single/` calls are being made

## Current Test Data:

There are 2 category 7 (FYI - Group) emails in the system:
- Email ID 37: "Track Your Order Here 🚚"
- Expected recommendation: "Orders" folder (NEW)
