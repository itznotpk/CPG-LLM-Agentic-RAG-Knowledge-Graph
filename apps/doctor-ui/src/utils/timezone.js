/**
 * Timezone Utility Functions
 * ===========================
 * All timestamps should use UTC+08:00 (Malaysia/Singapore timezone)
 */

/**
 * Get current date/time as ISO string
 * JavaScript Date handles timezone internally - display functions use timeZone option
 * @returns {string} ISO string (UTC format, display converted to Asia/Singapore)
 */
export const getNowUTC8 = () => {
    return new Date().toISOString();
};

/**
 * Get current date in YYYY-MM-DD format (UTC+08:00)
 * @returns {string} Date string in YYYY-MM-DD format
 */
export const getTodayUTC8 = () => {
    const now = new Date();
    // Use Intl.DateTimeFormat to get the correct date in Asia/Singapore timezone
    const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Singapore' });
    return formatter.format(now); // Returns YYYY-MM-DD format
};

/**
 * Format a date object or string to UTC+08:00 display format
 * @param {Date|string} date - Date to format
 * @param {boolean} includeTime - Whether to include time
 * @returns {string} Formatted date string
 */
export const formatDateUTC8 = (date, includeTime = true) => {
    if (!date) return '';

    const dateObj = typeof date === 'string' ? new Date(date) : date;
    if (isNaN(dateObj.getTime())) return '';

    const options = {
        timeZone: 'Asia/Singapore', // UTC+08:00
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        ...(includeTime ? { hour: '2-digit', minute: '2-digit', hour12: false } : {})
    };

    return dateObj.toLocaleString('en-US', options);
};

/**
 * Format date for display with only date (no time)
 * @param {Date|string} date - Date to format
 * @returns {string} Formatted date string (e.g., "Jan 15, 2026")
 */
export const formatDateOnlyUTC8 = (date) => formatDateUTC8(date, false);
