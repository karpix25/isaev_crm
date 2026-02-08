import crypto from 'crypto';

/**
 * Verify Telegram initData signature
 * Based on: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
 */
export function verifyTelegramWebAppData(
    initData: string,
    botToken: string
): { valid: boolean; data?: Record<string, any> } {
    try {
        const urlParams = new URLSearchParams(initData);
        const hash = urlParams.get('hash');
        urlParams.delete('hash');

        if (!hash) {
            return { valid: false };
        }

        // Sort params alphabetically and create data-check-string
        const dataCheckArr: string[] = [];
        urlParams.forEach((value, key) => {
            dataCheckArr.push(`${key}=${value}`);
        });
        dataCheckArr.sort();
        const dataCheckString = dataCheckArr.join('\n');

        // Create secret key from bot token
        const secretKey = crypto
            .createHmac('sha256', 'WebAppData')
            .update(botToken)
            .digest();

        // Calculate hash
        const calculatedHash = crypto
            .createHmac('sha256', secretKey)
            .update(dataCheckString)
            .digest('hex');

        if (calculatedHash !== hash) {
            return { valid: false };
        }

        // Parse user data
        const userData = urlParams.get('user');
        if (!userData) {
            return { valid: false };
        }

        const user = JSON.parse(userData);
        return {
            valid: true,
            data: {
                id: user.id,
                firstName: user.first_name,
                lastName: user.last_name,
                username: user.username,
                photoUrl: user.photo_url,
            },
        };
    } catch (error) {
        console.error('Telegram verification error:', error);
        return { valid: false };
    }
}
