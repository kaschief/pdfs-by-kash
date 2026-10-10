// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Kaschief
//
// Draws the user's chosen Pdfs by Kash icon on the app's Dock tile while the
// app is NOT running (macOS loads NSDockTilePlugIn bundles into the Dock for
// apps kept in the Dock). While the app runs, it sets its own icon via
// NSApp.applicationIconImage, so this plug-in only covers the gap.
//
// It lives inside the signed .app (Contents/PlugIns), so choosing an icon never
// modifies the bundle or its signature.

#import <AppKit/AppKit.h>

static NSString *const kAppDomain = @"com.kaschief.pdfsbykash";
static NSString *const kIconKey = @"AppIcon";
static NSString *const kDefaultIcon = @"squish";
static NSString *const kChangedNotification = @"com.kaschief.pdfsbykash.AppIconChanged";

@interface PdfsByKashDockTilePlugIn : NSObject <NSDockTilePlugIn>
@property(nonatomic, strong) NSDockTile *tile;  // not "dockTile": its setter would be -setDockTile: and recurse
@property(nonatomic, strong) id observer;
@end

@implementation PdfsByKashDockTilePlugIn

- (NSString *)chosenIconName {
    CFPreferencesAppSynchronize((__bridge CFStringRef)kAppDomain);
    id value = CFBridgingRelease(
        CFPreferencesCopyAppValue((__bridge CFStringRef)kIconKey, (__bridge CFStringRef)kAppDomain));
    if (![value isKindOfClass:[NSString class]]) return kDefaultIcon;
    // Only plain slugs: never let a preference value walk out of the folder.
    NSCharacterSet *allowed = [NSCharacterSet characterSetWithCharactersInString:
                                                  @"abcdefghijklmnopqrstuvwxyz-"];
    NSString *slug = (NSString *)value;
    if (slug.length == 0 ||
        [slug rangeOfCharacterFromSet:allowed.invertedSet].location != NSNotFound) {
        return kDefaultIcon;
    }
    return slug;
}

- (NSURL *)iconsDirectory {
    // .../Pdfs by Kash.app/Contents/PlugIns/<this>.docktileplugin
    NSURL *contents = [[[NSBundle bundleForClass:self.class].bundleURL
        URLByDeletingLastPathComponent] URLByDeletingLastPathComponent];
    return [contents URLByAppendingPathComponent:@"Resources/AppIcons" isDirectory:YES];
}

- (void)refresh {
    NSDockTile *tile = self.tile;
    if (tile == nil) return;
    NSString *name = [self chosenIconName];
    if ([name isEqualToString:kDefaultIcon]) {
        tile.contentView = nil;  // the bundle icon already is Squish
        [tile display];
        return;
    }
    NSURL *url = [[self iconsDirectory] URLByAppendingPathComponent:
                                            [name stringByAppendingPathExtension:@"png"]];
    NSImage *image = [[NSImage alloc] initWithContentsOfURL:url];
    if (image == nil) {
        tile.contentView = nil;
    } else {
        NSImageView *view = [NSImageView imageViewWithImage:image];
        view.imageScaling = NSImageScaleProportionallyUpOrDown;
        tile.contentView = view;
    }
    [tile display];
}

- (void)setDockTile:(NSDockTile *)dockTile {
    if (self.observer != nil) {
        [[NSDistributedNotificationCenter defaultCenter] removeObserver:self.observer];
        self.observer = nil;
    }
    self.tile = dockTile;
    if (dockTile == nil) return;  // app removed from the Dock
    __weak typeof(self) weakSelf = self;
    self.observer = [[NSDistributedNotificationCenter defaultCenter]
        addObserverForName:kChangedNotification
                    object:nil
                     queue:[NSOperationQueue mainQueue]
                usingBlock:^(NSNotification *note) {
                  [weakSelf refresh];
                }];
    [self refresh];
}

- (void)dealloc {
    if (self.observer != nil) {
        [[NSDistributedNotificationCenter defaultCenter] removeObserver:self.observer];
    }
}

@end
