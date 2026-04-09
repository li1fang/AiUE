#include "PMXEquipmentBlueprintLibrary.h"

#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Actor.h"
#include "PMXCharacterEquipmentComponent.h"
#include "PMXEquipmentReflection.h"

UPMXCharacterEquipmentComponent* UPMXEquipmentBlueprintLibrary::FindOrAddEquipmentComponent(AActor* Actor)
{
    if (!Actor)
    {
        return nullptr;
    }

    UPMXCharacterEquipmentComponent* Existing = Actor->FindComponentByClass<UPMXCharacterEquipmentComponent>();
    if (Existing)
    {
        return Existing;
    }

    UPMXCharacterEquipmentComponent* Created = NewObject<UPMXCharacterEquipmentComponent>(Actor, TEXT("PMXCharacterEquipmentComponent"));
    if (!Created)
    {
        return nullptr;
    }

    Created->RegisterComponent();
    Actor->AddInstanceComponent(Created);
    return Created;
}

bool UPMXEquipmentBlueprintLibrary::SetEquipmentAttachSocket(AActor* Actor, FName SocketName)
{
    UPMXCharacterEquipmentComponent* Component = FindOrAddEquipmentComponent(Actor);
    if (!Component)
    {
        return false;
    }

    Component->SetAttachSocketName(SocketName);
    return true;
}

USkeletalMeshComponent* UPMXEquipmentBlueprintLibrary::EquipWeaponMesh(AActor* Actor, USkeletalMesh* WeaponMesh)
{
    return EquipWeaponMeshToSocket(Actor, WeaponMesh, TEXT("WeaponSocket"));
}

USkeletalMeshComponent* UPMXEquipmentBlueprintLibrary::EquipWeaponMeshToSocket(AActor* Actor, USkeletalMesh* WeaponMesh, FName SocketName)
{
    UPMXCharacterEquipmentComponent* Component = FindOrAddEquipmentComponent(Actor);
    if (!Component)
    {
        return nullptr;
    }

    Component->SetAttachSocketName(SocketName);
    Component->SetDesiredWeaponMesh(WeaponMesh);
    return Component->ApplyWeaponMeshToOwner();
}

USkeletalMeshComponent* UPMXEquipmentBlueprintLibrary::ApplyEquipmentLoadout(AActor* Actor, UPMXEquipmentLoadoutAsset* LoadoutAsset)
{
    if (!LoadoutAsset)
    {
        return nullptr;
    }

    const FPMXEquipmentLoadoutEntry& Loadout = LoadoutAsset->Loadout;
    return EquipWeaponMeshToSocket(Actor, Loadout.WeaponMesh, Loadout.AttachSocketName);
}
