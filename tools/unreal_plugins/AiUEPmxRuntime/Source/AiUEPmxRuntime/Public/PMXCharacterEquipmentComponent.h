#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "PMXEquipmentReflection.h"
#include "PMXCharacterEquipmentComponent.generated.h"

class USceneComponent;
class USkeletalMeshComponent;
class UStaticMeshComponent;
class UNiagaraComponent;

UCLASS(ClassGroup=(PMXPipeline), BlueprintType, Blueprintable, meta=(BlueprintSpawnableComponent))
class AIUEPMXRUNTIME_API UPMXCharacterEquipmentComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UPMXCharacterEquipmentComponent();

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    void SetDesiredWeaponMesh(USkeletalMesh* InWeaponMesh);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    void SetDesiredItemForSlot(const FPMXEquipmentSlotBindingEntry& InBinding);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    void SetDesiredSlotBindings(const TArray<FPMXEquipmentSlotBindingEntry>& InBindings);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    TArray<FPMXEquipmentSlotBindingEntry> GetDesiredSlotBindings() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    USkeletalMesh* GetDesiredWeaponMesh() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    void SetAttachSocketName(FName InAttachSocketName);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    FName GetAttachSocketName() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    USceneComponent* ApplyItemForSlot(FName SlotName);

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    void ApplySlotBindings();

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    USkeletalMeshComponent* ApplyWeaponMeshToOwner();

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    USceneComponent* GetManagedComponentForSlot(FName SlotName) const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    USkeletalMeshComponent* GetManagedWeaponMeshComponent() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    TArray<FPMXEquipmentSlotConflictEntry> GetSlotConflicts() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    TArray<FPMXEquipmentSlotAttachState> GetResolvedSlotAttachStates() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    FName GetResolvedAttachSocketName() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    bool HasResolvedAttachSocket() const;

    UFUNCTION(BlueprintCallable, Category="PMXPipeline")
    FString GetAttachResolutionMode() const;

protected:
    virtual void BeginPlay() override;

private:
    void MirrorLegacyWeaponState();
    int32 FindSlotBindingIndex(FName SlotName) const;
    void UpsertDesiredBinding(const FPMXEquipmentSlotBindingEntry& InBinding);
    void RecordSlotConflict(const FPMXEquipmentSlotBindingEntry& PreviousBinding, const FPMXEquipmentSlotBindingEntry& IncomingBinding);
    FPMXEquipmentSlotBindingEntry BuildWeaponBinding(USkeletalMesh* InWeaponMesh) const;
    FString NormalizeItemKind(const FString& ItemKind, const FPMXEquipmentSlotBindingEntry& Binding) const;
    FPMXEquipmentSlotAttachState* FindSlotAttachState(FName SlotName);
    const FPMXEquipmentSlotAttachState* FindSlotAttachState(FName SlotName) const;
    FPMXEquipmentSlotAttachState& UpsertSlotAttachState(FName SlotName);
    FName ManagedComponentNameForSlot(FName SlotName, const FString& NormalizedItemKind) const;
    USceneComponent* FindExistingManagedComponent(FName SlotName, const FString& NormalizedItemKind) const;
    USceneComponent* EnsureManagedComponentForSlot(const FPMXEquipmentSlotBindingEntry& Binding, const FString& NormalizedItemKind);
    USkeletalMeshComponent* FindOwnerMeshComponent() const;
    FName ResolveAttachSocketName(USkeletalMeshComponent* OwnerMesh, FName SlotName, FName RequestedSocketName, FPMXEquipmentSlotAttachState* AttachState = nullptr);
    void RefreshManagedMeshComponent(USceneComponent* MeshComponent) const;

private:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline", meta=(AllowPrivateAccess="true"))
    TObjectPtr<USkeletalMesh> DesiredWeaponMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline", meta=(AllowPrivateAccess="true"))
    TArray<FPMXEquipmentSlotBindingEntry> DesiredSlotBindings;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline", meta=(AllowPrivateAccess="true"))
    FName AttachSocketName = TEXT("WeaponSocket");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PMXPipeline", meta=(AllowPrivateAccess="true"))
    bool bCreateComponentIfMissing = true;

    UPROPERTY(Transient)
    TMap<FName, TObjectPtr<USceneComponent>> ManagedComponentsBySlot;

    UPROPERTY(Transient)
    TArray<FPMXEquipmentSlotConflictEntry> SlotConflicts;

    UPROPERTY(Transient)
    TArray<FPMXEquipmentSlotAttachState> SlotAttachStates;

    UPROPERTY(Transient)
    FName ResolvedAttachSocketName = NAME_None;

    UPROPERTY(Transient)
    bool bResolvedAttachSocketExists = false;

    UPROPERTY(Transient)
    FString AttachResolutionMode = TEXT("unresolved");
};
