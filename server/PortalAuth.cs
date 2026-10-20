using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.EntityFrameworkCore;

static class PortalAuth {
    public static string UserId(ClaimsPrincipal p) => p.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
    public static string Hash(string token) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(token)));
    public static bool ValidPassword(string? p) => p is { Length: >= 12 and <= 128 };
    public static bool ValidEmail(string? value) => value is { Length: > 3 and <= 254 } && System.Net.Mail.MailAddress.TryCreate(value, out var parsed) && parsed.Address == value;
    public static async Task<bool> CanAccess(ClaimsPrincipal p, PortalDb db, string building) =>
        p.Identity?.IsAuthenticated == true && await db.Buildings.AnyAsync(b => b.Id == building) &&
        !await db.WorkspaceDeletions.AnyAsync(d => d.BuildingId == building) &&
        (p.IsInRole("admin") || await db.Grants.AnyAsync(g => g.BuildingId == building && g.UserId == UserId(p)));
    public static async Task Validate(CookieValidatePrincipalContext c) {
        var db = c.HttpContext.RequestServices.GetRequiredService<PortalDb>();
        var user = await db.Users.AsNoTracking().SingleOrDefaultAsync(u => u.Id == UserId(c.Principal!));
        if (user is null || user.Disabled) { c.RejectPrincipal(); return; }
        var sessionId = c.Principal!.FindFirstValue("sid");
        var validSession = !string.IsNullOrEmpty(sessionId) && await db.Sessions.AsNoTracking().AnyAsync(s => s.Id == sessionId && s.UserId == user.Id && s.RevokedUtc == null && s.ExpiresUtc > DateTime.UtcNow);
        if (user is { Disabled: false, Role: "admin" } && validSession) return;
        var device = c.Request.Cookies["Flamingo.Device"];
        if (!validSession || user.SessionId is null || user.SessionId != sessionId || string.IsNullOrEmpty(device) || user.DeviceHash != Hash(device)) c.RejectPrincipal();
    }
}
