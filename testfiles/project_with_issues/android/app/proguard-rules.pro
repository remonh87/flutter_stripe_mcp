# Incomplete ProGuard rules — missing several required Stripe entries.
# The check should report the missing -dontwarn lines and the -keep rule.

-dontwarn com.stripe.android.pushProvisioning.PushProvisioningActivityStarter
-dontwarn kotlinx.parcelize.Parceler
