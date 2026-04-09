#include "PMXCharacterHost.h"

#include "Components/SkeletalMeshComponent.h"
#include "PMXCharacterEquipmentComponent.h"
#include "PMXEquipmentReflection.h"

APMXCharacterHost::APMXCharacterHost()
{
    PrimaryActorTick.bCanEverTick = false;
    EquipmentComponentClass = UPMXCharacterEquipmentComponent::StaticClass();
}

UPMXCharacterEquipmentComponent* APMXCharacterHost::EnsureEquipmentComponent()
{
    if (RuntimeEquipmentComponent)
    {
        return RuntimeEquipmentComponent;
    }

    RuntimeEquipmentComponent = FindComponentByClass<UPMXCharacterEquipmentComponent>();
    if (RuntimeEquipmentComponent)
    {
        return RuntimeEquipmentComponent;
    }

    UClass* DesiredClass = EquipmentComponentClass ? EquipmentComponentClass.Get() : UPMXCharacterEquipmentComponent::StaticClass();
    RuntimeEquipmentComponent = NewObject<UPMXCharacterEquipmentComponent>(this, DesiredClass, TEXT("PMXEquipmentComponent"));
    if (!RuntimeEquipmentComponent)
    {
        return nullptr;
    }

    RuntimeEquipmentComponent->RegisterComponent();
    AddInstanceComponent(RuntimeEquipmentComponent);
    return RuntimeEquipmentComponent;
}

void APMXCharacterHost::ApplyCharacterMesh()
{
    if (USkeletalMeshComponent* CharacterMeshComponent = GetMesh())
    {
        CharacterMeshComponent->SetSkeletalMesh(CharacterMeshAsset);
        CharacterMeshComponent->SetVisibility(true, true);
        CharacterMeshComponent->SetHiddenInGame(false, true);
    }
}

void APMXCharacterHost::ApplyConfiguredLoadout()
{
    ApplyCharacterMesh();

    UPMXCharacterEquipmentComponent* EquipmentComponent = EnsureEquipmentComponent();
    if (!EquipmentComponent)
    {
        return;
    }

    if (DefaultLoadoutAsset)
    {
        const FPMXEquipmentLoadoutEntry& Loadout = DefaultLoadoutAsset->Loadout;
        EquipmentComponent->SetAttachSocketName(Loadout.AttachSocketName);
        EquipmentComponent->SetDesiredWeaponMesh(Loadout.WeaponMesh);
        if (Loadout.WeaponMesh)
        {
            EquipmentComponent->ApplyWeaponMeshToOwner();
        }
        return;
    }

    if (EquipmentComponent->GetDesiredWeaponMesh())
    {
        EquipmentComponent->ApplyWeaponMeshToOwner();
    }
}

void APMXCharacterHost::SetCharacterMeshAsset(USkeletalMesh* InCharacterMeshAsset)
{
    CharacterMeshAsset = InCharacterMeshAsset;
    ApplyCharacterMesh();
}

void APMXCharacterHost::SetDefaultLoadoutAsset(UPMXEquipmentLoadoutAsset* InDefaultLoadoutAsset)
{
    DefaultLoadoutAsset = InDefaultLoadoutAsset;
}

void APMXCharacterHost::SetEquipmentComponentClass(TSubclassOf<UPMXCharacterEquipmentComponent> InEquipmentComponentClass)
{
    EquipmentComponentClass = InEquipmentComponentClass;
    if (!EquipmentComponentClass)
    {
        EquipmentComponentClass = UPMXCharacterEquipmentComponent::StaticClass();
    }
}

UPMXCharacterEquipmentComponent* APMXCharacterHost::GetRuntimeEquipmentComponent() const
{
    return RuntimeEquipmentComponent;
}

void APMXCharacterHost::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    ApplyConfiguredLoadout();
}

void APMXCharacterHost::BeginPlay()
{
    Super::BeginPlay();
    ApplyConfiguredLoadout();
}
