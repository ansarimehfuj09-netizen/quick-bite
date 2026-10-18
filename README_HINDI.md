# Quick Bite – Real Ordering App (Hindi Guide)

Is folder mein customer app, owner dashboard (`/owner`), secure login aur database sab kuch hai.

## LIVE KARNE KE 3 STEP (Render par)

### Step 1 – GitHub par upload
1. github.com/new kholo, naam `quick-bite`, **Private** chuno, Create.
2. "uploading an existing file" par click karo.
3. ZIP extract karke **andar ki saari files aur `static` folder** drag-drop karo
   (main.py, requirements.txt, render.yaml, README_HINDI.md, static).
4. "Commit changes" dabao.

### Step 2 – Render par deploy
1. render.com par GitHub se login karo.
2. New + → **Blueprint** → apna `quick-bite` repo chuno → Apply.
3. Jab `OWNER_PASSWORD` pooche, apna **strong password** daalo (yaad rakhna).
4. 3-5 minute mein link milega: `https://quick-bite-xxxx.onrender.com`

### Step 3 – Use karo
- Customer link: `https://quick-bite-xxxx.onrender.com`
- Owner (aapka phone): `https://quick-bite-xxxx.onrender.com/owner` → password daalo → "Sound" dabao.
- Dono ko Chrome mein "Add to Home Screen" kar lo.

## ZAROORI BAATEN
- Render ka **free plan** 15 min idle rehne par app sula deta hai (pehla order slow khulega) aur free database kuch time baad expire ho sakta hai.
  Real customers ke liye Render dashboard mein web service aur database dono **paid plan** par daalo.
- Menu/daam badalne ke liye `main.py` ka `MENU` badlo (GitHub par edit karke commit karo).
- Delivery fee, minimum order etc. Render → Environment mein badal sakte ho:
  `DELIVERY_FEE`, `FREE_DELIVERY_ABOVE`, `MIN_ORDER`, `RESTAURANT_NAME`.
- Abhi sirf Cash/UPI **on delivery** hai. Online payment (Razorpay) alag step hai.
- Real launch se pehle apna privacy policy / FSSAI details dikhana mat bhoolna.
