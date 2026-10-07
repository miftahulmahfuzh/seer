# Sean receipts

Every Gotrade Order Summary screenshot uploaded to Sean, exactly as received, named by the
SHA-256 of its bytes (`sean_orders.image_sha256`). Written by `web/app/api/sean/orders` on
upload; never edited or deleted. Vercel skips building this branch (`web/vercel.json` turns deploys off here, and the project's ignored-build-step command skips it too).
